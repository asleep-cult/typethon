"""This module converts the values of an abstract syntax tree into atoms.

Example atomizer outputs:

1 + 1 => IntegerAtom(2)
10 if True else 0 => IntegerAtom(10)
10 if condition else 0.0 => UnionAtom([IntegerAtom(10), FloatAtom(0.0)])
"""
from .atomizer import *
from .bridge import *
