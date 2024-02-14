#!/bin/python3

'''Supplies a Packer object that exports data in a compacted form'''

#> Imports
import typing
from ast import literal_eval
from fractions import Fraction
from enum import Enum, IntEnum
from collections import abc, namedtuple
#</Imports

#> Header >/
__all__ = ('Packer', 'ReduceNamedtuple')

ReduceNamedtuple = Enum('ReduceNamedTuple', ('FAIL', 'AS_DICT', 'AS_TUPLE', 'AS_NAMEDTUPLE'))
TypeKey = IntEnum('TypeKey', (
    # Numeric
    'FALSE', 'TRUE', 'INT', 'FLOAT', 'COMPLEX', 'FRACTION',
    # Sequences
    ## Simple
    'BYTES', 'STR',
    ## Recursive
    'TUPLE', 'SET', 'DICT', 'NAMEDTUPLE',
    # Other keys
    'CONSTANT', 'REPR',
))
Constants = (None, NotImplemented, Ellipsis)

class Packer:
    '''Exports and imports data in a compacted form'''
    __slots__ = ('fraction_precision', 'optimize_do_blanking', 'try_reduce_objects', 'reduce_namedtuple', 'str_encoding',
                 '_size_base', '_type_to_pfx', '_pfx_to_type')

    STR_ENCODING = 'UTF-8'
    FRACTION_PRECISION = Fraction.limit_denominator.__defaults__[0]
    
    def __init__(self, optimize_do_blanking: bool = True, fraction_precision: int = FRACTION_PRECISION,
                 try_reduce_objects: bool = False, reduce_namedtuple: ReduceNamedtuple = ReduceNamedtuple.AS_NAMEDTUPLE,
                 str_encoding: str = STR_ENCODING):
        # Config
        self.optimize_do_blanking = True
        self.fraction_precision = fraction_precision
        self.try_reduce_objects = try_reduce_objects
        self.reduce_namedtuple = reduce_namedtuple
        self.str_encoding = str_encoding
        # Type
        self._size_base = 255 - len(TypeKey)
        self._type_to_pfx = {t: bytes((self._size_base + n,)) for n,t in enumerate(TypeKey)}
        self._pfx_to_type = {p: t for t,p in self._type_to_pfx.items()}
