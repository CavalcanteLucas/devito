

def make_ops_ast(expr):

    # from IPython import embed; embed()  

    if expr.is_Equality:
        (lhs, rhs) = expr.args
        print(lhs,end='\n > '); make_ops_ast(lhs)
        print(rhs,end='\n > '); make_ops_ast(rhs)
    elif expr.is_Indexed:
        # from IPython import embed; embed()  
        print('helo darkness my old friend')
    else:
        print('night fever')