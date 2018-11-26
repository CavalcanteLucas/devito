from sympy import Function
from numpy import float32

from devito.operator import OperatorRunnable
from devito.ir.iet.utils import find_offloadable_trees
from devito.ir.iet.nodes import Expression, Iteration, Call, ClusterizedEq
from devito.ir.iet.visitors import FindNodes
from devito.ir.iet import Callable, Transformer, Node, Section, List, MetaCall
from devito.types import Array, Symbol
from devito import Dimension
from devito.symbolics import Macro

from devito.types import Object

from devito.symbolics.extended_sympy import ListInitializer
from devito.ops.utils import namespace
from devito.ops.types import OPSDeclObject
from devito.ops.transformer import opsit, make_ops_ast

from ctypes import c_double

__all__ = ['Operator']

"""
We will start considering that each `Operator` will have 
only one `offloadable_tree`, only one `Grid`, and only one `Expression`.
"""


class Operator(OperatorRunnable):

    """
    A special :class:`OperatorCore` to JIT-compile and run operators through OPS.
    """

    _default_includes = OperatorRunnable._default_includes + \
        ['ops_seq.h', 'ops_lib_cpp.h']

    def _specialize_iet(self, iet, **kwargs):
        ops_data = []

        # Define ops_init call.
        ops_init_Object = Call(name=namespace['call-ops_init'],
                               params=[0, Macro('NULL'), 1])
        # Define ops_exit call.
        ops_exit_Object = Call(name=namespace['call-ops_exit'],
                               params=[])

        # Inserts both ops init and exit into the iet.
        iterationInitial = FindNodes(Iteration).visit(iet)[0]
        iet = Transformer({iterationInitial: List(
            body=[ops_init_Object, iterationInitial, ops_exit_Object])}).visit(iet)

        for (section, trees) in (find_offloadable_trees(iet).items()):
            node = trees[0].root
            expressions = [e for e in FindNodes(Expression).visit(node)]
            iterations = [i for i in FindNodes(Iteration).visit(node)]
            expr = expressions[0].expr

            # Generate OPS kernels
            kernels = opsit(trees)

            # Mark the kernels as calls.
            for index, kernel in enumerate(kernels):
                self._func_table[namespace['ops-kernel'](index)] = MetaCall(kernel, True)

            # iet = Transformer({iterations[0]:ops_par_loop}).visit(iet)
            # pprint(iet)
            # iet = Transformer({section:kernels[0]}).visit(iet)

            dim = 2  # Generalize
            ops_grid_Object = OPSDeclObject(dtype=namespace['type-ops_grid'],
                                            name=namespace['name-ops_grid'],
                                            value=Function(namespace['call-ops_grid'])
                                            (dim,
                                             namespace['name-ops_grid']))

            limits = []
            for i in iterations:
                limits.append(str(i.limits[1]))
            ops_size_Object = ListInitializer(limits)
            ops_base_Object = ListInitializer(['0', '0'])

            halo_mapper = {}
            fun = expressions[0].functions[0]  # TO DO: generalize for more Functions
            # for d, o in zip(fun.dimensions, fun._extent_halo):
            #     if d.is_Time:
            #         pass
            #     else:
            #         halo_mapper.setdefault(fun, {})
            #         halo_mapper[fun].setdefault('left', []).append(-o.left)
            #         halo_mapper[fun].setdefault('right', []).append(o.right)
            # ops_negBound_Object = ListInitializer(list(map(str, halo_mapper[fun]['left'])))
            # ops_posBound_Object = ListInitializer(list(map(str, halo_mapper[fun]['right'])))

            # ops_dat_Object = OPSDeclObject(dtype = namespace['type-ops_dat'],
            #                                 name = namespace['name-ops_dat'](''),
            #                                 value = Function(namespace['call-ops_dat'])
            #                                         (ops_grid_Object,
            #                                          1,
            #                                          ops_size_Object,
            #                                          ops_base_Object,
            #                                          ops_negBound_Object,
            #                                          ops_posBound_Object,
            #                                          fun.name,
            #                                          'double',
            #                                          namespace['name-ops_dat']('')))

            ops_stencilWriterPts_Object = ListInitializer(['0', '0'])
            ops_stencilWriter_Object = OPSDeclObject(dtype=namespace['type-ops_stencil'],
                                                     name=namespace['name-ops_stencil'](
                                                         'writer'),
                                                     value=Function(
                                                         namespace['call-ops_stencil'])
                                                     (dim,
                                                      int(len(
                                                          (ops_stencilWriterPts_Object).params)/2),
                                                      ops_stencilWriterPts_Object,
                                                      namespace['name-ops_stencil']('writer')))

            ops_stencilReaderPts_Object = ListInitializer(
                ['0', '0', '0', '-1', '-1', '0'])  # This must be taken from the FD
            ops_stencilReader_Object = OPSDeclObject(dtype=namespace['type-ops_stencil'],
                                                     name=namespace['name-ops_stencil'](
                                                         'reader'),
                                                     value=Function(
                                                         namespace['call-ops_stencil'])
                                                     (dim,
                                                      int(len(
                                                          (ops_stencilReaderPts_Object).params)/2),
                                                      ops_stencilReaderPts_Object,
                                                      namespace['name-ops_stencil']('writer')))

            ops_parLoop_Object = Call(name=namespace['call-ops_par_loop'],
                                      params=[2, Array(name='u', dimensions=[Dimension(name='t0')], dtype=float32)])

            mapper = {iterations[0]: ops_parLoop_Object}

            ops_data.append(ops_grid_Object)
            # ops_data.append(ops_dat_Object)
            ops_data.append(ops_stencilWriter_Object)
            ops_data.append(ops_stencilReader_Object)
            iet = Transformer(mapper).visit(iet)  # ops_data.append(ops_parLoop_Object)
            # ops_data.append(ops_exit_Object)

        # Temporary.
        # for od in ops_data:
        #     print(od)

        # raise NotImplementedError
        return iet
