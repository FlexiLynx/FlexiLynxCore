#!/bin/python3

'''Supplies a Packer object that exports data in a compacted form'''

#> Imports
import math
import typing
import struct
import dataclasses
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

    S_DOUBLE = struct.Struct('!d')
    S_COMPLEX = struct.Struct('!dd')
    
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

    # Size encoding
    @staticmethod
    def _n_to_base(n: int, base: int) -> bytes:
        return bytes(((n % (base**p))) // (base**(p-1)) for p in range(1, math.ceil(1+math.log(n+1, base))))
    @staticmethod
    def _n_from_base(bn: bytes, base: int) -> int:
        if not bn: return 0
        return sum(d*(base**p) for p,d in enumerate(bn))
    def encode_size(self, s: int) -> bytes:
        '''Encodes an integer in self._size_base'''
        return self._i_to_base(s, self._size_base) if s else b''
    def decode_size(self, bs: bytes) -> int:
        '''Decodes an integer from self._size_base'''
        return self._i_from_base(bs, self._size_base) if bs else 0

    def _try_encode_literal(self, o: object) -> str | None:
        r = repr(o)
        try: lo = literal_eval(r)
        except Exception: return None
        if o == lo: return r
        return None
    def encode(self, o: object) -> tuple[TypeKey, bytes]:
        '''Encodes an object and returns it and its type-key'''
        match o:
            # Numeric
            case bool():
                return ((TypeKey.TRUE if o else TypeKey.FALSE), b'')
            case int():
                return (TypeKey.INT, o.to_bytes((o.bit_length() + 8) // 8, signed=True)
                        if (o or not self.optimize_do_blanking) else b'')
            case float():
                if self.optimize_do_blanking and not o: return (TypeKey.FLOAT, b'')
                # encode as a Fraction
                fenc = self.encode(Fraction(o))[1]
                # check if structs are smaller
                if len(fenc) < self.S_DOUBLE.size: return (TypeKey.FLOAT, fenc)
                # if so, use structs
                try: return (TypeKey.FLOAT, self.S_DOUBLE.pack(o))
                except struct.error: return (TypeKey.FLOAT, fenc) # structs failed, use Fraction
            case complex():
                if self.optimize_do_blanking and not o: return(TypeKey.COMPLEX, b'')
                # recursively pack
                pak = self.pack(o.real, o.imag)
                # check if structs are smaller
                if len(pak) < self.S_COMPLEX.size: return (TypeKey.COMPLEX, pak)
                # if so, use structs
                try: return (TypeKey.COMPLEX, self.S_COMPLEX.pack(o))
                except struct.error: return (TypeKey.COMPLEX, pak) # structs failed, use recursive pack
            case Fraction():
                n,d = o.limit_denominator(self.fraction_precision).as_integer_ratio()
                np = n.to_bytes((n.bit_length() + 8) // 8, signed=True) \
                     if (n or not self.optimize_do_blanking) else b'' # numerator is signed and could be 0
                dp = self._i_to_base(d, 254) # denominator is not and can't be 0, use the extra bit gained from signing for delimiter
                return (TypeKey.FRACTION, np + b'\xFF' + dp)
            # Sequences
            ## Simple
            case bytes() | bytearray(): return (TypeKey.BYTES, bytes(o))
            case str(): return (TypeKey.STR, o.encode(self.str_encoding))
            ## Recursive
            case abc.Sequence():
                if hasattr(o, '_asdict') and (self.reduce.namedtuple != ReduceNamedtuple.AS_TUPLE):
                    # if it's a namedtuple and we don't treat namedtuples as tuples
                    if self.reduce_namedtuple is ReduceNamedtuple.FAIL:
                        raise TypeError('Refusing to reduce a namedtuple when reduce_namedtuple is FAIL')
                    if self.reduce_namedtuple is ReduceNamedtuple.AS_DICT: # render as a dict
                        return self.encode(o._asdict())
                    if self.reduce_namedtuple is ReduceNamedtuple.AS_NAMEDTUPLE:
                        return (TypeKey.NAMEDTUPLE, self.pack(o.__class__.__name__, o.__module__, *sum(tuple(o._asdict().items()), start=())))
                    raise ValueError(f'reduce_namedtuple is an illegal value: {self.reduce_namedtuple!r}')
                return (TypeKey.TUPLE, self.pack(*(so for so in o)))
            case abc.Set():
                return (TypeKey.SET, self.pack(*(so for so in o)))
            case abc.Mapping():
                return (TypeKey.DICT, self.pack(*sum(tuple(o.items()), start=())))
        # Constants
        if o in Constants:
            return (TypeKey.CONSTANT, b'' if (o is None) and self.optimize_do_blanking else bytes((Constants.index(o),)))
        # Literals
        if (r := self._try_encode_literal(o)) is not None: # object can be literalized
            return (TypeKey.REPR, r.encode(self.STR_ENCODING))
        # Try reducing objects
        if self.try_reduce_objects:
            # Dataclasses
            if dataclasses.is_dataclass(o):
                return self.encode(dataclasses.asdict(o))
            # Reduce arbitrary objects through __dict__ and __slots__
            if hasattr(o, '__dict__') or hasattr(o, '__slots__'):
                return self.encode(getattr(o, '__dict__', {}) | {a: getattr(o, a) for a in getattr(o, '__slots__', ())})
        # Fail
        raise TypeError(f'Cannot encode object {o!r} of type {type(o).__qualname__!r}')

            
