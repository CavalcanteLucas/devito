from sympy import Function

from devito.operator import OperatorRunnable
from devito.ir.iet.utils import find_offloadable_trees
from devito.ir.iet.nodes import Expression, Iteration, Call, ClusterizedEq
from devito.ir.iet.visitors import FindNodes
from devito.ir.iet import Callable,Transformer, Node, Section, List, MetaCall

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

    def _specialize_iet(self, iet, **kwargs):
        ops_data = []

        """
        First things first.
        """
        ops_init_Object = Call(name=namespace['call-ops_init'], 
                                params=(0, 'NULL', 1))            


        for (section, trees) in (find_offloadable_trees(iet).items()):
            node = trees[0].root
            expressions = [e for e in FindNodes(Expression).visit(node)]           
            iterations = [i for i in FindNodes(Iteration).visit(node)]
            expr = expressions[0].expr           

            # Generate OPS kernels
            kernels = opsit(trees)

            # iet = [kernels[0], iet]

            # Mark the kernels as calls.
            self._func_table[namespace['ops-kernel']] = MetaCall(kernels[0], True)

            from devito import pprint
            print('**********************************************************')
            pprint(kernels[0])
            print('**********************************************************')

            # pprint(iet)
            # print('**********************************************************')
            # pprint(trees)
            # print('**********************************************************')
            # pprint(expressions)
            # print('**********************************************************')

            # my_ops_expr = [Expression(ClusterizedEq(kernels[0]))]

            # pprint(my_ops_expr)

            
            # iet = Transformer({expressions[0] : my_ops_expr}).visit(iet)
            # pprint(iet)


            """
            We need to create an `OPS grid`. 
            For a (x,y) spatial domain, that'd be something like: 
            "ops_block grid = ops_decl_block(2, "grid");"
            """
            dim = 2 # Generalize 
            ops_grid_Object = OPSDeclObject(dtype = namespace['type-ops_grid'],
                                            name = namespace['name-ops_grid'], 
                                            value = Function(namespace['call-ops_grid'])
                                                    (dim,
                                                     namespace['name-ops_grid']))

            limits = []
            for i in iterations:
                limits.append(str(i.limits[1]))
            ops_size_Object = ListInitializer(limits)
            ops_base_Object = ListInitializer(['0','0'])

            halo_mapper = {}
            fun = expressions[0].functions[0]  # TO DO: generalize for more Functions
            for d, o in zip(fun.dimensions, fun._extent_halo):
                if d.is_Time:
                    pass
                else:
                    halo_mapper.setdefault(fun, {})
                    halo_mapper[fun].setdefault('left', []).append(-o.left)
                    halo_mapper[fun].setdefault('right', []).append(o.right)
            ops_negBound_Object = ListInitializer(list(map(str, halo_mapper[fun]['left'])))
            ops_posBound_Object = ListInitializer(list(map(str, halo_mapper[fun]['right'])))

            ops_dat_Object = OPSDeclObject(dtype = namespace['type-ops_dat'],
                                            name = namespace['name-ops_dat'](''), 
                                            value = Function(namespace['call-ops_dat'])
                                                    (ops_grid_Object,
                                                     1,
                                                     ops_size_Object,
                                                     ops_base_Object,
                                                     ops_negBound_Object,
                                                     ops_posBound_Object,
                                                     fun.name,
                                                     'double',
                                                     namespace['name-ops_dat']('')))


            ops_stencilWriterPts_Object = ListInitializer(['0','0'])
            ops_stencilWriter_Object = OPSDeclObject(dtype = namespace['type-ops_stencil'],
                                            name = namespace['name-ops_stencil']('writer'), 
                                            value = Function(namespace['call-ops_stencil'])
                                                    (dim,
                                                     int(len((ops_stencilWriterPts_Object).params)/2),
                                                     ops_stencilWriterPts_Object,
                                                     namespace['name-ops_stencil']('writer')))

            ops_stencilReaderPts_Object = ListInitializer(['0','0','0','-1','-1','0']) # This must be taken from the FD
            ops_stencilReader_Object = OPSDeclObject(dtype = namespace['type-ops_stencil'],
                                            name = namespace['name-ops_stencil']('reader'), 
                                            value = Function(namespace['call-ops_stencil'])
                                                    (dim,
                                                     int(len((ops_stencilReaderPts_Object).params)/2),
                                                     ops_stencilReaderPts_Object,
                                                     namespace['name-ops_stencil']('writer')))
            
            ops_parLoop_Object = Call(name=namespace['call-ops_exit'], 
                                   params=('apply_stencil',         # this arg comes from ops_file.h
                                           'apply_stencil',         # this is just a str for internal debugging
                                           ops_grid_Object))
           
            """
            Last but not least.
            """
            ops_exit_Object = Call(name=namespace['call-ops_par_loop'], 
                                   params=None)
            
            ops_data.append(ops_init_Object)
            ops_data.append(ops_grid_Object)
            ops_data.append(ops_dat_Object)
            ops_data.append(ops_stencilWriter_Object)
            ops_data.append(ops_stencilReader_Object)
            ops_data.append(ops_parLoop_Object)
            ops_data.append(ops_exit_Object)

        # Temporary. 
        # for od in ops_data:
        #     print(od)

        # raise NotImplementedError
        return iet

