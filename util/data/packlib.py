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

    # Size encoding / decoding
    @staticmethod
    def _n_to_base(n: int, base: int) -> bytes:
        return bytes(((n % (base**p))) // (base**(p-1)) for p in range(1, math.ceil(1+math.log(n+1, base))))
    @staticmethod
    def _n_from_base(bn: bytes, base: int) -> int:
        if not bn: return 0
        return sum(d*(base**p) for p,d in enumerate(bn))
    def encode_size(self, s: int) -> bytes:
        '''Encodes an integer in self._size_base'''
        return self._n_to_base(s, self._size_base) if s else b''
    def decode_size(self, bs: bytes) -> int:
        '''Decodes an integer from self._size_base'''
        return self._n_from_base(bs, self._size_base) if bs else 0

    # Object encoding
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
                dp = self._n_to_base(d, 254) # denominator is not and can't be 0, use the extra bit gained from signing for delimiter
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
            return (TypeKey.REPR, r.encode(self.str_encoding))
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
    DONT_TRY_REPR = {TypeKey.FALSE, TypeKey.TRUE, TypeKey.BYTES, TypeKey.STR, TypeKey.REPR}
    def encode_plus(self, o: object) -> tuple[TypeKey, bytes]:
        '''Encodes the object `o`, then tries representing it in literal form; returns the shortest'''
        et,ev = self.encode(o)
        if et in self.DONT_TRY_REPR: return (et, ev)
        if ((let := self._try_encode_literal(o)) is None) \
               or (len(let) > len(ev)): return (et, ev)
        return (TypeKey.REPR, let.encode(self.str_encoding))
    # Archiving
    def sarchive(self, data: typing.Iterable[tuple[TypeKey, bytes]], stream: typing.BinaryIO):
        '''Archives encoded data into a stream'''
        for t,d in data:
            stream.write(self.encode_size(len(d)))
            stream.write(self._type_to_pfx[t])
            stream.write(d)
    def iarchive(self, data: typing.Iterable[tuple[TypeKey, bytes]]) -> typing.Iterator[bytes]:
        '''Archives encoded data, yielding each segment'''
        for t,d in data:
            yield self.encode_size(len(d)) + self._type_to_pfx[t] + d
    def archive(self, data: typing.Iterable[tuple[TypeKey, bytes]]) -> bytes:
        '''
            Archives encoded data, returning the entirety of its bytes
                Could use `.sarchive()` or `.iarchive()`, depending on the implementation.
                This implementation uses `.iarchive()`
        '''
        # Results of testing with CPython 3.12.1
        # on system `Linux luthien 6.7.4-arch1-1 #1 SMP PREEMPT_DYNAMIC Mon, 05 Feb 2024 22:07:49 +0000 x86_64 GNU/Linux`
        # over `10000000` iterations using `timeit.timeit()`
        # on a simple data set: `('str', b'bytes', 0, 1, 1.5, 1.2)`:
        # Method using `iarchive()` with `bytes.join()`: took ~142.56 seconds total, or an average of ~1.4256E-05 seconds per iteration
        # Method using `sarchive()` with `io.BytesIO`: took ~150.50 seconds total, or an average of ~1.505E-05 seconds per iteration
        # The difference seems to be negligable, but this implementation will use `.iarchive()` anyway
        return b''.join(self.iarchive(data))
    # Packing
    def spack(self, stream: typing.BinaryIO, *objects: object):
        '''Packs a sequence of objects into a stream'''
        self.sarchive(stream, map(self.encode_plus, objects))
    def ipack(self, *objects: object) -> typing.Iterator[bytes]:
        '''Packs a sequence of objects into bytes, yielding each set of bytes'''
        return self.iarchive(map(self.encode_plus, objects))
    def pack(self, *objects) -> bytes:
        '''
            Packs a sequence of objects into bytes
                Could use `.sarchive()`, `.iarchive()`, or `.archive()`, depending on the implementation.
                This implementation uses `.archive()`
        '''
        return self.archive(map(self.encode_plus, objects))

    # Decoding
    TYPEKEY_TO_NULL_CONSTRUCTOR = {
        TypeKey.FALSE: False.__bool__, TypeKey.TRUE: True.__bool__,
        TypeKey.INT: int, TypeKey.FLOAT: float, TypeKey.COMPLEX: complex, TypeKey.FRACTION: Fraction,
        TypeKey.BYTES: bytes, TypeKey.STR: str,
        TypeKey.TUPLE: tuple, TypeKey.SET: frozenset, TypeKey.DICT: dict,
        TypeKey.NAMEDTUPLE: NotImplemented, # namedtuple reduction should never result in blanked data
        TypeKey.CONSTANT: type(None),
        TypeKey.REPR: NotImplemented, # literal reduction should never result in blanked data
    }
    def decode(self, t: TypeKey, e: bytes) -> object:
        '''
            Given a `TypeKey` `t`, and its data `e`, returns the original[1] object
             [1]Note that this will not be the exact same object if it has been reduced in any way,
                as well as that mutable objects will be different and may be converted to be immutable
        '''
        if not e:
            # blanked data, or some singleton values
            if (c := self.TYPEKEY_TO_NULL_CONSTRUCTOR[t]) is not NotImplemented:
                return c()
            raise TypeError(f'Corrupted data: TypeKey {t!r} does not support blanked data')
        match t:
            # Numeric
            case TypeKey.TRUE | TypeKey.FALSE:
                raise ValueError(f'TypeKey {t!r} does not support arguments: `e`')
            case TypeKey.INT:
                int.from_bytes(e, signed=True)
            case TypeKey.FLOAT:
                if len(e) == self.S_FLOAT.size: # must be packed
                    return self.S_FLOAT.unpack(e)
                return float(self.decode(TypeKey.FRACTION, e))
            case TypeKey.COMPLEX:
                if len(e) == self.S_COMPLEX.size: # must be packed
                    return complex(*self.S_COMPLEX.unpack(e))
                return complex(*self.unpack(e))
            case TypeKey.FRACTION:
                n,d = e.rsplit(b'\xFF', 1)
                return Fraction(int.from_bytes(n, signed=True), int.from_bytes(d, signed=False))
            # Sequences
            ## Simple
            case TypeKey.BYTES: return e
            case TypeKey.STR: return e.decode(self.str_encoding)
            ## Recursive
            case TypeKey.TUPLE: return self.unpack(e)
            case TypeKey.SET: return frozenset(self.unpack(e))
            case TypeKey.DICT: return dict(zip(e[::2], e[1::2]))
            case TypeKey.NAMEDTUPLE:
                clsname,modname,*items = self.unpack(e)
                return namedtuple(clsname, items[::2], module=modname)(items[1::2])
            # Constants
            case TypeKey.CONSTANT:
                if len(e) != 1: raise ValueError(f'Too much data for {t!r}: {e!r}')
                return Constants[e[0]]
            case TypeKey.REPR:
                return literal_eval(e.decode(self.str_encoding))
        raise TypeError(f'TypeKey {t!r} not recognized')
