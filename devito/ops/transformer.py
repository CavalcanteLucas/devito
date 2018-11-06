from sympy import Eq, symbols

from devito.ir.iet.nodes import Expression
from devito.ir.iet.visitors import FindNodes

from devito.ops.node_factory import ops_node_factory


def opsit(trees):
    """
    Populate the tree with OPS instructions.

    :param trees: A sequence of offloadable :class: `IterationTree`s, in which the 
                  Expressions are searched.                  
    """
    #Track all OPS kernels created
    processed = []
    for tree in trees:
        # All expressions whithin `tree`
        expressions = [i.expr for i in FindNodes(Expression).visit(tree.inner)]

         # Attach conditional expression for sub-domains
        conditions = [(i, []) for i in expressions]

        # Only one node factory for all expression so we can keep track 
        # of all kernels generated.
        nfops = ops_node_factory()    

        for k, v in conditions:
            ops_expr = make_ops_ast(k, nfops)
            print(ops_expr)

            if ops_expr is not None:
                processed.append(ops_expr)


def make_ops_ast(expr, nfops):

    def nary2binary(args, op):
        r = make_ops_ast(args[0], nfops)
        return r if len(args) == 1 else op(r, nary2binary(args[1:], op))

    if expr.is_Integer:
        return nfops.new_int_node(int(expr))
    elif expr.is_Float:
        return nfops.new_float_node(float(expr))
    elif expr.is_Rational:
        a, b = expr.as_numer_denom()
        return nfops.new_rational_node(float(a)/float(b))
    elif expr.is_Symbol:
        if expr.function.is_Dimension:
            return expr.name
    elif expr.is_Mul:
        return nary2binary(expr.args, nfops.new_mul_node)
    elif expr.is_Add:
        return nary2binary(expr.args, nfops.new_add_node)
    elif expr.is_Equality:
        # This is the endpoint. What exactly should I return here?!?!
        return (make_ops_ast(expr.lhs,nfops), make_ops_ast(expr.rhs,nfops))
    elif expr.is_Indexed:
        dimensions = [make_ops_ast(i, nfops) 
                      for i in expr.indices]     
        return nfops.new_grid(expr.name, dimensions)
    else:
        print(expr)
        raise NotImplementedError("Missing handler in Devito-OPS translation")
