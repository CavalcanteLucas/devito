from sympy import Function

from numpy import dtype

class ops_node_factory():
    '''
        Class responsible to generate ops nodes for building the OPS ast.
    '''

    def __init__(self):
        # Track all kernel created
        self.kernel_mapper = []
        # Map kernel parameters
        self.kernel_parameters = []
        # For each kernel, maps the variables to generate the OPS_ACC#
        self.all_symbols_mapper_per_kernel = {}
        # Kernel being generated
        self.current_kernel = None
        # OPS_ACC counter
        self.acc_counter = 0

    def new_const_number_node(self, number):
        self.all_symbols_mapper_per_kernel[self.current_kernel].append(number)
        print(self.all_symbols_mapper_per_kernel)

    def new_operation_node(self, operation):
        self.all_symbols_mapper_per_kernel[self.current_kernel].append(operation)
        print(self.all_symbols_mapper_per_kernel)

    def new_dimension_symbol_node(self, expr):
        symbol = None
        if expr not in self.all_symbols_mapper_per_kernel:

            parameter = '{0}_{1}'.format(
                expr.name,
                self.acc_counter
            )

            symbol = '{0}[OPS_ACC{1}({2})]'.format(
                parameter,
                self.acc_counter,
                'TODO')
            self.acc_counter += 1
        
        ## TODO: Get data type
        ## TODO: Identify OPS_READ and OPS_WRITE. OPS_READ should have a 'const' modifier.
        type = 'double'
        self.kernel_parameters.append(type + '*' + parameter)
        self.all_symbols_mapper_per_kernel[self.current_kernel].append(symbol)

        print(self.all_symbols_mapper_per_kernel)

    def new_kernel_node(self, expr):
        # from IPython import embed
        # embed()
        self.current_kernel = expr
        self.kernel_mapper.append(self.current_kernel)        
        self.all_symbols_mapper_per_kernel[self.current_kernel] = []
        print(self.kernel_mapper)
        
    def print_kernel(self, kernel):
        # Add kernel unique identification and expression.
        method_declaration = "void kernel_{0}({1})\n{{\n {2} \n}}".format(        
            self.kernel_mapper.index(kernel), 
            ', '.join(self.kernel_parameters),
            ''.join([str(i) for i in self.all_symbols_mapper_per_kernel[kernel]])
        )

        print(method_declaration)

        
    
