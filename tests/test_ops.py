import pytest
import numpy as np

from devito.ops.types import *

from devito import Grid, TimeFunction, Operator, Eq, configuration


pytestmark = pytest.mark.skipif(configuration['backend'] != 'ops',
                                reason="'ops' wasn't selected as backend on startup")


class TestOperatorSimple(object):
    """
    Test execution of simple Operators through OPS.
    """

    def test_ops_one_dimension_time_function(self):
        """
        Creates a simple one dimension grid with 0's and
        add 1's to the grid.
        """
        grid = Grid(shape=10)

        u = TimeFunction(name='u', grid=grid)

        eq = Eq(u.forward, u + 1.0)

        op = Operator(eq)

        op.apply(t=1)

        assert 'run_solution' in str(op)
        # Check that the domain size has actually been written to
        assert np.all(u.data[1] == 1.0)


class TestOPSDeclarations(object):
    """
    Tests each of OPS types such as ops_dat, ops_grid...
    """

    def test_ops_declarations(self):
        """
        Creates a simple one dimension grid with 0's and
        add 1's to the grid.
        """
        grid = Grid(shape=10)

        u = TimeFunction(name='u', grid=grid)

        eq = Eq(u.forward, u + 1.0)

        op = Operator(eq)

        # Checks if ops init declaration
        assert 'ops_init' in str(op)
        # Checks if ops_exit declaration
        assert 'ops_exit();' in str(op)
        # Checks ops_dat declaration
        assert 'ops_dat dat_u' in str(op)
        # Checks ops_grid declaration
        assert 'ops_block grid' in str(op)
