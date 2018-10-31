from sympy import Eq, symbols


def make_ops_ast(expr, nfops):
    if expr.is_Integer:
        return nfops.new_const_number_node(int(expr))
    elif expr.is_Float:
        return nfops.new_const_number_node(float(expr))
    elif expr.is_Rational:
        a, b = expr.as_numer_denom()
        return nfops.new_const_number_node(float(a)/float(b))
    elif expr.is_Mul:
        (lhs, rhs) = expr.args
        make_ops_ast(lhs,nfops)
        nfops.new_operation_node('*')
        make_ops_ast(rhs,nfops)
    elif expr.is_Add:
        (lhs, rhs) = expr.args
        make_ops_ast(lhs,nfops)
        nfops.new_operation_node('+')
        make_ops_ast(rhs,nfops)
    elif expr.is_Equality:
        (lhs, rhs) = expr.args           
        make_ops_ast(lhs, nfops)     
        nfops.new_operation_node('=')
        make_ops_ast(rhs, nfops)     
    elif expr.is_Indexed:
        #function = expr.function
        # print('function', function)
        # print('function index', function.indices)      
        nfops.new_dimension_symbol_node(expr)  
        ##[make_ops_ast(i.root, nfops) for i in function.indices]
    else:
        print(expr)
        raise NotImplementedError("Missing handler in Devito-OPS translation")
