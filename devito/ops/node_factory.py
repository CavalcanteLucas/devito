from sympy import Eq, Symbol, Add, Mul, Integer, Float, Rational

from devito.ops.utils import namespace

class Ops_node_factory():
    """
        Class responsible to generate ops expression for building the OPS ast.
    """

    def __init__(self):
        self.grids = {}        

    def new_int_node(self, number):
        """
            Creates a new sympy integer object.

            :param number: integer number.
        """
        # Should I test for integer?
        return Integer(number)      

    def new_float_node(self, number):
        """
            Creates a new sympy float object.

            :param number: float number.
        """
        # Should I test for float?
        return Float(number)

    def new_rational_node(self, num, den):
        """
            Creates a new sympy rational object.

            :param num: Rational numerator.
            :param den: Rational denominator. 
        """
        return Rational(num, den)

    def new_add_node(self, lhs, rhs):
        """
            Creates a new sympy Add object.

            :param lhs: Left hand side of the sum.
            :param rhs: Right hand side of the sum.
        """
        return Add(lhs, rhs)

    def new_mul_node(self, lhs,rhs):
        """
            Creates a new sympy Mul object.

            :param lhs: Left hand side of the multiplication.
            :param rhs: Right hand side of the multiplication.
        """
        return Mul(lhs,rhs)

    def new_grid(self, name, dimensions):       
        """
            Creates a new grid access given a  variable name and its dimensions.
            If the pair grid name and time dimension was alredy created, it will return
            the stored value associated with this pair.

            :param name: grid name.
            :param dimensions: time and space dimensions to access the grid. Its expected
                               the first parameter be the time dimension.
        """ 

        grid_id = '%s%s' % (name,dimensions[0])

        if grid_id in self.grids:
            symbol = self.grids[grid_id]
        else:            
            # FIXME Where can I get the 0,0 info?
            symbol = Symbol('%s[%s%s(%s)]' % 
                            (grid_id, namespace['ops_acc'], 
                             str(len(self.grids)), '0,0')) 
                     
            self.grids[grid_id] = symbol            

        return symbol


    def new_equation_node(self, *args):
        """
            Creates a new sympy equation with the provided arguments.

            :param *args: arguments to construct the new equation.
        """
        return Eq(*args)




        
    
