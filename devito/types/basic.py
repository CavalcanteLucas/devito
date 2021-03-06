import abc
from collections import namedtuple
from ctypes import POINTER, Structure, byref
from functools import reduce
from math import ceil
from operator import mul

import numpy as np
import sympy
from sympy.core.assumptions import _assume_rules
from cached_property import cached_property
from cgen import Struct, Value
from frozendict import frozendict

from devito.data import default_allocator
from devito.parameters import configuration
from devito.symbolics import Add
from devito.tools import (EnrichedTuple, Evaluable, Pickable,
                          ctypes_to_cstr, dtype_to_cstr, dtype_to_ctype)
from devito.types.args import ArgProvider
from devito.types.caching import Cached

__all__ = ['Symbol', 'Scalar', 'Array', 'Indexed', 'Object',
           'LocalObject', 'CompositeObject']


class Basic(object):

    """
    Three relevant types inherit from this class:

        * AbstractSymbol: represents a scalar; may carry data; may be used
                          to build equations.
        * AbstractFunction: represents a discrete R^n -> R function; may
                            carry data; may be used to build equations.
        * AbstractObject: represents a generic object, for example a (pointer
                          to) data structure.

                                        Basic
                                          |
                    ------------------------------------------
                    |                     |                  |
             AbstractSymbol       AbstractFunction     AbstractObject

    All these subtypes must implement a number of methods/properties to enable
    code generation via the Devito compiler. These methods/properties are
    easily recognizable as their name starts with _C_.

    Notes
    -----
    The AbstractFunction sub-hierarchy is implemented in :mod:`dense.py`.
    """

    # Top hierarchy
    is_AbstractFunction = False
    is_AbstractSymbol = False
    is_AbstractObject = False

    # Symbolic objects created internally by Devito
    is_Symbol = False
    is_Array = False
    is_Object = False
    is_LocalObject = False

    # Created by the user
    is_Input = False
    # Scalar symbolic objects created by the user
    is_Dimension = False
    is_Constant = False
    # Tensor symbolic objects created by the user
    is_DiscreteFunction = False
    is_Function = False
    is_TimeFunction = False
    is_SparseTimeFunction = False
    is_SparseFunction = False
    is_PrecomputedSparseFunction = False
    is_PrecomputedSparseTimeFunction = False

    # Basic symbolic object properties
    is_Scalar = False
    is_Tensor = False

    # Some other properties
    is_PerfKnob = False  # Does it impact the Operator performance?

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        return

    @abc.abstractproperty
    def _C_name(self):
        """
        The C-level name of the object.

        Returns
        -------
        str
        """
        return

    @abc.abstractproperty
    def _C_typename(self):
        """
        The C-level type of the object.

        Returns
        -------
        str
        """
        return

    @abc.abstractproperty
    def _C_typedata(self):
        """
        The C-level type of the data values.

        Returns
        -------
        str
        """
        return

    @abc.abstractproperty
    def _C_ctype(self):
        """
        The C-level type of the object, as a ctypes object, suitable for type
        checking when calling functions via ctypes.

        Returns
        -------
        ctypes type
        """
        return

    @property
    def _C_typedecl(self):
        """
        The C-level struct declaration representing the object.

        Returns
        -------
        cgen.Struct or None
            None if the object C type can be expressed with a basic C type,
            such as float or int.
        """
        return


class AbstractSymbol(sympy.Symbol, Basic, Pickable, Evaluable):

    """
    Base class for scalar symbols.

    The hierarchy is structured as follows

                             AbstractSymbol
                                   |
                 -------------------------------------
                 |                                   |
             DataSymbol                            Symbol
                 |                                   |
         ----------------                   -------------------
         |              |                   |                 |
      Constant   DefaultDimension         Scalar          Dimension
                                                    <:mod:`dimension.py`>

    All symbols can be used to build equations. However, while DataSymbol
    carries data, Symbol is a pure symbolic object.

    Constant, DefaultDimension, and Dimension (and most of its subclasses) are
    part of the user API; Scalar, instead, is only used internally by Devito.

    DefaultDimension and Dimension define a problem dimension (in other words,
    an "iteration space"). They can be used to index into Functions. For more
    information, refer to :mod:`dimension.py`.
    """

    is_AbstractSymbol = True
    is_Symbol = True

    @classmethod
    def _filter_assumptions(cls, **kwargs):
        """Extract sympy.Symbol-specific kwargs."""
        assumptions = {}
        for i in list(kwargs):
            if i in _assume_rules.defined_facts:
                assumptions[i] = kwargs.pop(i)
        return assumptions, kwargs

    def __new__(cls, *args, **kwargs):
        name = kwargs.get('name') or args[0]
        assumptions, kwargs = cls._filter_assumptions(**kwargs)

        # Create the new Symbol
        # Note: use __xnew__ to bypass sympy caching
        newobj = sympy.Symbol.__xnew__(cls, name, **assumptions)

        # Initialization
        newobj._dtype = cls.__dtype_setup__(**kwargs)
        newobj.__init_finalize__(*args, **kwargs)

        return newobj

    @classmethod
    def __dtype_setup__(cls, **kwargs):
        """Extract the object data type from ``kwargs``."""
        return kwargs.get('dtype', np.int32)

    def __init__(self, *args, **kwargs):
        # no-op, the true init is performed by __init_finalize__
        pass

    def __init_finalize__(self, *args, **kwargs):
        self._is_const = kwargs.get('is_const', False)

    @property
    def dtype(self):
        """The data type of the object."""
        return self._dtype

    @property
    def indices(self):
        return ()

    @property
    def shape(self):
        return ()

    @property
    def ndim(self):
        return 0

    @property
    def symbolic_shape(self):
        return ()

    @property
    def base(self):
        return self

    @property
    def function(self):
        return self

    @property
    def evaluate(self):
        return self

    def indexify(self):
        return self

    @property
    def is_const(self):
        """
        True if the symbol value cannot be modified within an Operator (and thus
        its value is provided by the user directly from Python-land), False otherwise.
        """
        return self._is_const

    @property
    def _C_name(self):
        return self.name

    @property
    def _C_typename(self):
        return '%s%s' % ('const ' if self.is_const else '',
                         dtype_to_cstr(self.dtype))

    @property
    def _C_typedata(self):
        return dtype_to_cstr(self.dtype)

    @property
    def _C_ctype(self):
        return dtype_to_ctype(self.dtype)

    def _subs(self, old, new, **hints):
        """
        This stub allows sympy.Basic.subs to operate on an expression
        involving devito Scalars.  Ordinarily the comparisons between
        devito subclasses of sympy types are quite strict.
        """
        try:
            if old.name == self.name:
                return new
        except AttributeError:
            pass

        return self

    # Pickling support
    _pickle_args = []
    _pickle_kwargs = ['name', 'dtype', 'is_const']
    __reduce_ex__ = Pickable.__reduce_ex__


class Symbol(AbstractSymbol, Cached):

    """
    A scalar symbol, cached by both Devito and SymPy, which does not carry
    any data.

    Notes
    -----
    A Symbol may not be in the SymPy cache, but still be present in the
    Devito cache. This is because SymPy caches operations, rather than
    actual objects.
    """

    @classmethod
    def _cache_key(cls, *args, **kwargs):
        args = list(args)
        key = {}

        # The base type is necessary, otherwise two objects such as
        # `Scalar(name='s')` and `Dimension(name='s')` would have the same key
        key['cls'] = cls

        # The name is always present, and added as if it were an arg
        key['name'] = kwargs.pop('name', None) or args.pop(0)

        # From the args
        key['args'] = tuple(args)

        # From the kwargs
        key.update(kwargs)

        return frozendict(key)

    def __new__(cls, *args, **kwargs):
        key = cls._cache_key(*args, **kwargs)
        obj = cls._cache_get(key)

        if obj is not None:
            return obj

        # Not in cache. Create a new Symbol via sympy.Symbol
        name = kwargs.get('name') or args[0]
        assumptions, kwargs = cls._filter_assumptions(**kwargs)

        # Note: use __xnew__ to bypass sympy caching
        newobj = sympy.Symbol.__xnew__(cls, name, **assumptions)

        # Initialization
        newobj._dtype = cls.__dtype_setup__(**kwargs)
        newobj.__init_finalize__(*args, **kwargs)

        # Store new instance in symbol cache
        Cached.__init__(newobj, key)

        return newobj

    __hash__ = Cached.__hash__


class DataSymbol(AbstractSymbol, Cached):

    """
    A scalar symbol, cached by both Devito and SymPy, which carries data.
    """

    @classmethod
    def _cache_key(cls, *args, **kwargs):
        """A DataSymbol caches on the class type itself."""
        return cls

    def __new__(cls, *args, **kwargs):
        key = cls._cache_key(*args, **kwargs)
        obj = cls._cache_get(key)

        if obj is not None:
            return obj

        # Not in cache. Create a new Symbol via sympy.Symbol
        name = kwargs.get('name') or args[0]
        assumptions, kwargs = cls._filter_assumptions(**kwargs)

        # Create new, unique type instance from cls and the symbol name
        newcls = type(name, (cls,), dict(cls.__dict__))

        # Create the new Symbol and invoke __init__
        newobj = sympy.Symbol.__new__(newcls, name, **assumptions)

        # Initialization
        newobj._dtype = cls.__dtype_setup__(**kwargs)
        newobj.__init_finalize__(*args, **kwargs)

        # Store new instance in symbol cache
        Cached.__init__(newobj, newcls)

        return newobj

    __hash__ = Cached.__hash__

    # Pickling support

    @property
    def _pickle_reconstruct(self):
        return self.__class__.__base__


class Scalar(Symbol, ArgProvider):

    """
    Like a Symbol, but in addition it can pass runtime values to an Operator.

    Parameters
    ----------
    name : str
        Name of the symbol.
    dtype : data-type, optional
        Any object that can be interpreted as a numpy data type. Defaults
        to ``np.float32``.
    is_const : bool, optional
        True if the symbol value cannot be modified within an Operator,
        False otherwise. Defaults to False.
    **assumptions
        Any SymPy assumptions, such as ``nonnegative=True``. Refer to the
        SymPy documentation for more information.
    """

    is_Scalar = True

    @classmethod
    def __dtype_setup__(cls, **kwargs):
        return kwargs.get('dtype', np.float32)


class AbstractFunction(sympy.Function, Basic, Cached, Pickable, Evaluable):

    """
    Base class for tensor symbols, cached by both SymPy and Devito. It inherits
    from and mimick the behaviour of a sympy.Function.

    The hierarchy is structured as follows

                         AbstractFunction
                                |
                 ---------------------------------
                 |                               |
         DiscreteFunction                      Array
                 |
         ----------------------------------------
         |                                      |
         |                           AbstractSparseFunction
         |                                      |
         |               -----------------------------------------------------
         |               |                      |                            |
      Function     SparseFunction   AbstractSparseTimeFunction  PrecomputedSparseFunction
         |               |                      |                            |
         |               |   ------------------------------------     --------
         |               |   |                                  |     |
    TimeFunction  SparseTimeFunction                 PrecomputedSparseTimeFunction

    There are five relevant AbstractFunction sub-types: ::

        * Array: A function that does not carry data. Usually created by the DSE.
        * Function: A space-varying discrete function, which carries user data.
        * TimeFunction: A time- and space-varying discrete function, which carries
                        user data.
        * SparseFunction: A space-varying discrete function representing "sparse"
                          points, i.e. points that are not aligned with the
                          computational grid.
        * SparseTimeFunction: A time- and space-varying function representing "sparse"
                          points, i.e. points that are not aligned with the
                          computational grid.
        * PrecomputedSparseFunction: A SparseFunction that uses a custom interpolation
                                     scheme, instead of linear interpolators.
        * PrecomputedSparseTimeFunction: A SparseTimeFunction that uses a custom
                                         interpolation scheme, instead of linear
                                         interpolators.
    """

    is_AbstractFunction = True

    @classmethod
    def _cache_key(cls, *args, **kwargs):
        """An AbstractFunction caches on the class type itself."""
        return cls

    def __new__(cls, *args, **kwargs):
        options = kwargs.get('options', {})

        key = cls._cache_key(*args, **kwargs)
        obj = cls._cache_get(key)

        if obj is not None:
            newobj = sympy.Function.__new__(cls, *args, **options)
            newobj.__init_cached__(key)
            return newobj

        # Not in cache. Create a new Function via sympy.Function
        name = kwargs.get('name')
        indices = cls.__indices_setup__(**kwargs)

        # Create new, unique type instance from cls and the symbol name
        newcls = type(name, (cls,), dict(cls.__dict__))

        # Create the new Function object and invoke __init__
        newobj = sympy.Function.__new__(newcls, *indices, **options)

        # Initialization. The following attributes must be available
        # when executing __init_finalize__
        newobj._name = name
        newobj._indices = indices
        newobj._shape = cls.__shape_setup__(**kwargs)
        newobj._dtype = cls.__dtype_setup__(**kwargs)
        newobj.__init_finalize__(*args, **kwargs)

        # All objects cached on the AbstractFunction `newobj` keep a reference
        # to `newobj` through the `function` field. Thus, all indexified
        # object will point to `newobj`, the "actual Function".
        newobj.function = newobj

        # Store new instance in symbol cache
        Cached.__init__(newobj, newcls)
        return newobj

    def __init__(self, *args, **kwargs):
        # no-op, the true init is performed by __init_finalize__
        pass

    def __init_finalize__(self, *args, **kwargs):
        # Setup halo and padding regions
        self._is_halo_dirty = False
        self._halo = self.__halo_setup__(**kwargs)
        self._padding = self.__padding_setup__(**kwargs)

    __hash__ = Cached.__hash__

    @classmethod
    def __indices_setup__(cls, **kwargs):
        """Extract the object indices from ``kwargs``."""
        return ()

    @classmethod
    def __shape_setup__(cls, **kwargs):
        """Extract the object shape from ``kwargs``."""
        return ()

    @classmethod
    def __dtype_setup__(cls, **kwargs):
        """Extract the object data type from ``kwargs``."""
        return None

    def __halo_setup__(self, **kwargs):
        return tuple(kwargs.get('halo', [(0, 0) for i in range(self.ndim)]))

    def __padding_setup__(self, **kwargs):
        return tuple(kwargs.get('padding', [(0, 0) for i in range(self.ndim)]))

    @cached_property
    def _honors_autopadding(self):
        """
        True if the actual padding is greater or equal than whatever autopadding
        would produce, False otherwise.
        """
        autopadding = self.__padding_setup__(autopadding=True)
        return all(l0 >= l1 and r0 >= r1
                   for (l0, r0), (l1, r1) in zip(self.padding, autopadding))

    @property
    def name(self):
        """The name of the object."""
        return self._name

    @property
    def indices(self):
        """The indices (aka dimensions) of the object."""
        return self._indices

    @property
    def dimensions(self):
        """Tuple of Dimensions representing the object indices."""
        return self.indices

    @property
    def shape(self):
        """The shape of the object."""
        return self._shape

    @property
    def dtype(self):
        """The data type of the object."""
        return self._dtype

    @property
    def ndim(self):
        """The rank of the object."""
        return len(self.indices)

    @property
    def symbolic_shape(self):
        """
        The symbolic shape of the object. This includes the domain, halo, and
        padding regions. While halo and padding are known quantities (integers),
        the domain size is given as a symbol.
        """
        halo = [Add(*i) for i in self._size_halo]
        padding = [Add(*i) for i in self._size_padding]
        domain = [i.symbolic_size for i in self.indices]
        ret = tuple(Add(i, j, k) for i, j, k in zip(domain, halo, padding))
        return EnrichedTuple(*ret, getters=self.dimensions)

    @property
    def indexed(self):
        """The wrapped IndexedData object."""
        return IndexedData(self.name, shape=self.shape, function=self.function)

    @property
    def _mem_external(self):
        """
        True if the associated data was/is/will be allocated directly
        from Python (e.g., via NumPy arrays), False otherwise.
        """
        return False

    @property
    def _mem_stack(self):
        """
        True if the associated data should be allocated on the stack, False otherwise.
        """
        return False

    @property
    def _mem_heap(self):
        """
        True if the associated data was/is/will be allocated on the heap,
        False otherwise.
        """
        return False

    @property
    def size(self):
        """
        The number of elements this object is expected to store in memory.
        Note that this would need to be combined with self.dtype to give the actual
        size in bytes.
        """
        return reduce(mul, self.shape)

    @property
    def halo(self):
        return self._halo

    @property
    def padding(self):
        return self._padding

    @property
    def is_const(self):
        """
        True if the carried data values cannot be modified within an Operator,
        False otherwise.
        """
        return False

    @property
    def _C_name(self):
        return "%s_vec" % self.name

    @property
    def _C_typedata(self):
        return dtype_to_cstr(self.dtype)

    @cached_property
    def _size_domain(self):
        """Number of points in the domain region."""
        return EnrichedTuple(*self.shape, getters=self.dimensions)

    @cached_property
    def _size_halo(self):
        """Number of points in the halo region."""
        left = tuple(zip(*self._halo))[0]
        right = tuple(zip(*self._halo))[1]

        Size = namedtuple('Size', 'left right')
        sizes = tuple(Size(i, j) for i, j in self._halo)

        return EnrichedTuple(*sizes, getters=self.dimensions, left=left, right=right)

    @cached_property
    def _size_owned(self):
        """Number of points in the owned region."""
        left = tuple(self._size_halo.right)
        right = tuple(self._size_halo.left)

        Size = namedtuple('Size', 'left right')
        sizes = tuple(Size(i.right, i.left) for i in self._size_halo)

        return EnrichedTuple(*sizes, getters=self.dimensions, left=left, right=right)

    @cached_property
    def _size_padding(self):
        """Number of points in the padding region."""
        left = tuple(zip(*self._padding))[0]
        right = tuple(zip(*self._padding))[1]

        Size = namedtuple('Size', 'left right')
        sizes = tuple(Size(i, j) for i, j in self._padding)

        return EnrichedTuple(*sizes, getters=self.dimensions, left=left, right=right)

    @cached_property
    def _size_nopad(self):
        """Number of points in the domain+halo region."""
        sizes = tuple(i+sum(j) for i, j in zip(self._size_domain, self._size_halo))
        return EnrichedTuple(*sizes, getters=self.dimensions)

    @cached_property
    def _size_nodomain(self):
        """Number of points in the padding+halo region."""
        left = tuple(i for i, _ in np.add(self._halo, self._padding))
        right = tuple(i for _, i in np.add(self._halo, self._padding))

        Size = namedtuple('Size', 'left right')
        sizes = tuple(Size(i, j) for i, j in np.add(self._halo, self._padding))

        return EnrichedTuple(*sizes, getters=self.dimensions, left=left, right=right)

    @cached_property
    def _offset_domain(self):
        """Number of points before the first domain element."""
        offsets = tuple(np.add(self._size_padding.left, self._size_halo.left))
        return EnrichedTuple(*offsets, getters=self.dimensions)

    @cached_property
    def _offset_halo(self):
        """Number of points before the first and last halo elements."""
        left = tuple(self._size_padding.left)
        right = tuple(np.add(np.add(left, self._size_halo.left), self._size_domain))

        Offset = namedtuple('Offset', 'left right')
        offsets = tuple(Offset(i, j) for i, j in zip(left, right))

        return EnrichedTuple(*offsets, getters=self.dimensions, left=left, right=right)

    @cached_property
    def _offset_owned(self):
        """Number of points before the first and last owned elements."""
        left = tuple(self._offset_domain)
        right = tuple(np.add(self._offset_halo.left, self._size_domain))

        Offset = namedtuple('Offset', 'left right')
        offsets = tuple(Offset(i, j) for i, j in zip(left, right))

        return EnrichedTuple(*offsets, getters=self.dimensions, left=left, right=right)

    @property
    def _data_alignment(self):
        """
        The base virtual address of the data carried by the object is a multiple
        of the alignment.
        """
        return default_allocator().guaranteed_alignment

    @property
    def evaluate(self):
        return self

    def indexify(self, indices=None):
        """Create a types.Indexed from the current object."""
        if indices is not None:
            return Indexed(self.indexed, *indices)

        # Get spacing symbols for replacement
        spacings = [i.spacing for i in self.indices]

        # Only keep the ones used as indices.
        spacings = [s for i, s in enumerate(spacings)
                    if s.free_symbols.intersection(self.args[i].free_symbols)]

        # Substitution for each index
        subs = dict([(s, 1) for s in spacings])

        # Indices after substitutions
        indices = [a.subs(subs) for a in self.args]

        return Indexed(self.indexed, *indices)

    def __getitem__(self, index):
        """Shortcut for ``self.indexed[index]``."""
        return self.indexed[index]

    # Pickling support
    _pickle_kwargs = ['name', 'dtype', 'halo', 'padding']
    __reduce_ex__ = Pickable.__reduce_ex__

    @property
    def _pickle_reconstruct(self):
        return self.__class__.__base__


class Array(AbstractFunction):
    """
    Tensor symbol representing an array in symbolic equations.

    An Array is very similar to a sympy.Indexed, though it also carries
    metadata essential for code generation.

    Parameters
    ----------
    name : str
        Name of the symbol.
    dimensions : tuple of Dimension
        Dimensions associated with the object.
    dtype : data-type, optional
        Any object that can be interpreted as a numpy data type. Defaults
        to ``np.float32``.
    halo : iterable of 2-tuples, optional
        The halo region of the object.
    padding : iterable of 2-tuples, optional
        The padding region of the object.
    scope : str, optional
        Control memory allocation. Allowed values: 'heap', 'stack'. Defaults
        to 'heap'.

    Warnings
    --------
    Arrays are created and managed directly by Devito (IOW, they are not
    expected to be used directly in user code).
    """

    is_Array = True
    is_Tensor = True

    def __new__(cls, *args, **kwargs):
        kwargs.update({'options': {'evaluate': False}})
        return AbstractFunction.__new__(cls, *args, **kwargs)

    def __init_finalize__(self, *args, **kwargs):
        super(Array, self).__init_finalize__(*args, **kwargs)

        self._scope = kwargs.get('scope', 'heap')
        assert self._scope in ['heap', 'stack']

    def __padding_setup__(self, **kwargs):
        padding = kwargs.get('padding')
        if padding is None:
            padding = [(0, 0) for _ in range(self.ndim)]
            if kwargs.get('autopadding', configuration['autopadding']):
                # Heuristic 1; Arrays are typically introduced for DSE-produced
                # temporaries, and are almost always used together with loop
                # blocking.  Since the typical block size is a multiple of the SIMD
                # vector length, `vl`, padding is made such that the NODOMAIN size
                # is a multiple of `vl` too

                # Heuristic 2: the right-NODOMAIN size is not only a multiple of
                # `vl`, but also guaranteed to be *at least* greater or equal than
                # `vl`, so that the compiler can tweak loop trip counts to maximize
                # the effectiveness of SIMD vectorization

                # Let UB be a function that rounds up a value `x` to the nearest
                # multiple of the SIMD vector length
                vl = configuration['platform'].simd_items_per_reg(self.dtype)
                ub = lambda x: int(ceil(x / vl)) * vl

                fvd_halo_size = sum(self.halo[-1])
                fvd_pad_size = (ub(fvd_halo_size) - fvd_halo_size) + vl

                padding[-1] = (0, fvd_pad_size)
            return tuple(padding)
        elif isinstance(padding, int):
            return tuple((0, padding) for _ in range(self.ndim))
        elif isinstance(padding, tuple) and len(padding) == self.ndim:
            return tuple((0, i) if isinstance(i, int) else i for i in padding)
        else:
            raise TypeError("`padding` must be int or %d-tuple of ints" % self.ndim)

    @classmethod
    def __indices_setup__(cls, **kwargs):
        return tuple(kwargs['dimensions'])

    @classmethod
    def __dtype_setup__(cls, **kwargs):
        return kwargs.get('dtype', np.float32)

    @property
    def shape(self):
        return self.symbolic_shape

    @property
    def scope(self):
        return self._scope

    @property
    def _mem_stack(self):
        return self._scope == 'stack'

    @property
    def _mem_heap(self):
        return self._scope == 'heap'

    @property
    def _C_typename(self):
        return ctypes_to_cstr(POINTER(dtype_to_ctype(self.dtype)))

    @property
    def free_symbols(self):
        return super().free_symbols - {d for d in self.dimensions if d.is_Default}

    def update(self, **kwargs):
        self._shape = kwargs.get('shape', self.shape)
        self._indices = kwargs.get('dimensions', self.indices)
        self._dtype = kwargs.get('dtype', self.dtype)
        self._halo = kwargs.get('halo', self._halo)
        self._padding = kwargs.get('padding', self._padding)
        self._scope = kwargs.get('scope', self._scope)
        assert self._scope in ['heap', 'stack']

    # Pickling support
    _pickle_kwargs = AbstractFunction._pickle_kwargs + ['dimensions', 'scope']


# Objects belonging to the Devito API not involving data, such as data structures
# that need to be passed to external libraries


class AbstractObject(Basic, sympy.Basic, Pickable):

    """
    Symbol representing a generic pointer object.
    """

    is_AbstractObject = True

    def __new__(cls, *args, **kwargs):
        obj = sympy.Basic.__new__(cls)
        obj.__init__(*args, **kwargs)
        return obj

    def __init__(self, name, dtype):
        self.name = name
        self.dtype = dtype

    def __repr__(self):
        return self.name

    __str__ = __repr__

    def _hashable_content(self):
        return (self.name, self.dtype)

    @property
    def free_symbols(self):
        return {self}

    @property
    def _C_name(self):
        return self.name

    @property
    def _C_typename(self):
        return ctypes_to_cstr(self.dtype)

    @property
    def _C_ctype(self):
        return self.dtype

    @property
    def function(self):
        return self

    # Pickling support
    _pickle_args = ['name', 'dtype']
    __reduce_ex__ = Pickable.__reduce_ex__


class Object(AbstractObject, ArgProvider):

    """
    Symbol representing a generic pointer object, provided by an outer scope.
    """

    is_Object = True

    def __init__(self, name, dtype, value=None):
        super(Object, self).__init__(name, dtype)
        self.value = value

    @property
    def _arg_names(self):
        return (self.name,)

    def _arg_defaults(self):
        if callable(self.value):
            return {self.name: self.value()}
        else:
            return {self.name: self.value}

    def _arg_values(self, args=None, **kwargs):
        """
        Produce runtime values for this Object after evaluating user input.

        Parameters
        ----------
        args : dict, optional
            Known argument values.
        **kwargs
            Dictionary of user-provided argument overrides.
        """
        if self.name in kwargs:
            return {self.name: kwargs.pop(self.name)}
        else:
            return self._arg_defaults()


class CompositeObject(Object):

    """
    Symbol representing a pointer to a composite type (e.g., a C struct),
    provided by an outer scope.
    """

    _dtype_cache = {}

    @classmethod
    def _generate_unique_dtype(cls, pname, pfields):
        dtype = POINTER(type(pname, (Structure,), {'_fields_': pfields}))
        key = (pname, tuple(pfields))
        return cls._dtype_cache.setdefault(key, dtype)

    def __init__(self, name, pname, pfields, value=None):
        dtype = CompositeObject._generate_unique_dtype(pname, pfields)
        value = self.__value_setup__(dtype, value)
        super(CompositeObject, self).__init__(name, dtype, value)

    def __value_setup__(self, dtype, value):
        return value or byref(dtype._type_())

    @property
    def pfields(self):
        return tuple(self.dtype._type_._fields_)

    @property
    def pname(self):
        return self.dtype._type_.__name__

    @property
    def fields(self):
        return [i for i, _ in self.pfields]

    def _hashable_content(self):
        return (self.name, self.pfields)

    @cached_property
    def _C_typedecl(self):
        return Struct(self.pname, [Value(ctypes_to_cstr(j), i) for i, j in self.pfields])

    # Pickling support
    _pickle_args = ['name', 'pname', 'pfields']
    _pickle_kwargs = []


class LocalObject(AbstractObject):

    """
    Symbol representing a generic pointer object, defined in the local scope.
    """

    is_LocalObject = True


# Extended SymPy hierarchy follows, for essentially two reasons:
# - To keep track of `function`
# - To override SymPy caching behaviour


class IndexedData(sympy.IndexedBase, Pickable):

    """
    Wrapper class that inserts a pointer to the symbolic data object.
    """

    def __new__(cls, label, shape=None, function=None):
        # Make sure `label` is a devito.Symbol, not a sympy.Symbol
        if isinstance(label, str):
            label = Symbol(name=label, dtype=function.dtype)
        obj = sympy.IndexedBase.__new__(cls, label, shape)
        obj.function = function
        return obj

    def func(self, *args):
        obj = super(IndexedData, self).func(*args)
        obj.function = self.function
        return obj

    def __getitem__(self, indices, **kwargs):
        """Produce a types.Indexed, rather than a sympy.Indexed."""
        indexed = super(IndexedData, self).__getitem__(indices, **kwargs)
        return Indexed(*indexed.args)

    # Pickling support
    _pickle_kwargs = ['label', 'shape', 'function']
    __reduce_ex__ = Pickable.__reduce_ex__


class Indexed(sympy.Indexed):

    # The two type flags have changed in upstream sympy as of version 1.1,
    # but the below interpretation is used throughout the DSE and DLE to
    # identify Indexed objects. With the sympy-1.1 changes a new flag
    # obj.is_Indexed was introduced which should be preferred, but the
    # required changes are cumbersome and many...
    is_Symbol = False
    is_Atom = False

    is_Dimension = False

    def _hashable_content(self):
        return super(Indexed, self)._hashable_content() + (self.base.function,)

    @property
    def function(self):
        return self.base.function

    @property
    def dtype(self):
        return self.function.dtype

    @property
    def name(self):
        return self.function.name
