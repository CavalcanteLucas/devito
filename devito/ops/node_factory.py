from sympy import Function, Symbol, Add, Mul, Integer, Float, Rational

from numpy import dtype

from devito.ops.utils import namespace

class ops_node_factory():
    '''
        Class responsible to generate ops nodes for building the OPS ast.
    '''

    def __init__(self):
        self.grids = {}        

    def new_const_number_node(self, number):
        print('teste')

    def new_int_node(self, number):
        # Should I test for integer?
        return Integer(number)      

    def new_float_node(self, number):
        # Should I test for float?
        return Float(number)

    def new_rational_node(self, num, den):
        return Rational(num, den)

    def new_operation_node(self, operation):
        print('teste')

    def new_add_node(self, lhs, rhs):
        return Add(lhs, rhs)

    def new_mul_node(self, lhs,rhs):
        return Mul(lhs,rhs)

    def new_equation(self):
        self.ops_equation = Function()

    def new_grid(self, name, dimensions):       
        '''
            Creates a new grid access given a  variable name and its dimensions.
            If the pair grid name and time dimension was alredy created, it will return
            the stored value associated with this pair.

            :param name: grid name.
            :param dimensions: time and space dimensions to access the grid. Its expected
                               the first parameter be the time dimension.
        ''' 

        grid_id = name + dimensions[0]

        if grid_id in self.grids:
            symbol = self.grids[grid_id]
        else:            
            symbol = Symbol(str(name) + '[' + 
                     namespace['ops_acc'] + 
                      str(len(self.grids)) + '(' +
                     '0,0' + ')]')  # Where can I get this info?
                     
            self.grids[grid_id] = symbol            

        return symbol

        # if expr not in self.all_symbols_mapper_per_kernel:

        #     parameter = '{0}_{1}'.format(
        #         expr.name,
        #         self.acc_counter
        #     )
        
        ## TODO: Get data type
        ## TODO: Identify OPS_READ and OPS_WRITE. OPS_READ should have a 'const' modifier.
        # param_type = 'double'
        # self.kernel_parameters.append(Symbol(symbol))
        # self.all_symbols_mapper_per_kernel[self.current_kernel].append(symbol)
        # print(self.all_symbols_mapper_per_kernel)



        
    
