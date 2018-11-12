from sympy import Eq, symbols

from numpy import float32

from devito.types import Array
from devito.dimension import Dimension

from devito.ir.iet import Callable
from devito.ir.iet.nodes import Expression, ClusterizedEq
from devito.ir.iet.visitors import FindNodes

from devito.ops.node_factory import Ops_node_factory
from devito.ops.utils import namespace



def opsit(trees):
    """
    Populate the tree with OPS instructions.

    :param trees: A sequence of offloadable :class: `IterationTree`s, in which the 
                  Expressions are searched.                  
    """
    #Track all OPS kernels created
    mapper = {}
    processed = []
    for tree in trees:
        # All expressions whithin `tree`
        expressions = [i.expr for i in FindNodes(Expression).visit(tree.inner)]

         # Attach conditional expression for sub-domains
        conditions = [(i, []) for i in expressions]

        # Only one node factory for all expression so we can keep track 
        # of all kernels generated.
        nfops = Ops_node_factory()    

        for k, v in conditions:
            ops_expr = make_ops_ast(k, nfops, mapper)
            ops_kernel = create_new_ops_kernel(ops_expr)

            processed.append(ops_kernel)

    return processed

def make_ops_ast(expr, nfops, mapper):

    def nary2binary(args, op):
        r = make_ops_ast(args[0], nfops, mapper)
        return r if len(args) == 1 else op(r, nary2binary(args[1:], op))

    if expr.is_Integer:
        return nfops.new_int_node(int(expr))
    elif expr.is_Float:
        return nfops.new_float_node(float(expr))
    elif expr.is_Rational:
        a, b = expr.as_numer_denom()
        return nfops.new_rational_node(float(a)/float(b))
    elif expr.is_Symbol:
        # FIXME Fabio's is adding this part to the mapper... should we?        
        if expr.function.is_Dimension:
            return nfops.new_symbol(expr.name)
    elif expr.is_Mul:
        return nary2binary(expr.args, nfops.new_mul_node)
    elif expr.is_Add:
        return nary2binary(expr.args, nfops.new_add_node)
    elif expr.is_Equality:
        if expr.lhs.is_Symbol:
            function = expr.lhs.base.function
            mapper[function] = make_ops_ast(expr.rhs,nfops, mapper)
        else:
            return nfops.new_equation_node(*[make_ops_ast(i, nfops, mapper)
                                             for i in expr.args])
    elif expr.is_Indexed:
        dimensions = [make_ops_ast(i, nfops, mapper) 
                      for i in expr.indices]     
        return nfops.new_grid(expr.name, dimensions)
    else:
        raise NotImplementedError("Missing handler in Devito-OPS translation")


def create_new_ops_kernel(expr):

    parameters = Array(name='ops', 
                dimensions=[Dimension(name='ut0'), Dimension(name='ut1')],
                dtype=float32)

    return Callable(namespace['ops-kernel'], 
                    Expression(ClusterizedEq(expr)),
                    namespace['ops-kernel-retval'],
                    [parameters] + list(parameters.shape),
                    ('static',))