#!/bin/python3

#> Imports
import io
import struct
import math
import weakref
import typing
import dataclasses
from ast import literal_eval
#</Imports

#> Header >/
__all__ = ('Packer', 'packer', 'pack', 'unpack')

class Packer:
    __slots__ = (
        'optimize_do_blanking',
        'try_reduce_objects',
        '_size_base',
        '_type_to_pfx', '_pfx_to_type',
        '_is_cached_instance', '_is_initted',
        '__dict__', # allow customizing class-vars on instances
        '__weakref__', # allow instance caching
    )

    STR_ENCODING = 'UTF-8'

    S_DOUBLE = struct.Struct('!d')
    S_COMPLEX = struct.Struct('!dd')

    TYPE_KEYS = ( # ordered simplest to most complex (sans Other)
        # Numerics
        False, True, int, float, complex,
        # Sequences
        ## Simple sequences (encoded as-is)
        bytes, str,
        ## Recursive sequences
        tuple, frozenset, dict,
        # Other keys
        None, repr,
    )

    _INSTANCE_CACHE = weakref.WeakValueDictionary() # instances have no state, so its safe to cache them

    def __new__(cls, *, do_cache_instance: bool = True, optimize_do_blanking: bool = True, try_reduce_objects: bool = False, **kwargs):
        if do_cache_instance:
            h = hash((do_cache_instance, optimize_do_blanking, try_reduce_objects, tuple(kwargs.items())))
            if (i := cls._INSTANCE_CACHE.get(h, None)) is not None: return i # cache hit
        self = super().__new__(cls)
        if do_cache_instance:
            cls._INSTANCE_CACHE[h] = self # cache miss, save it for next time
        self._is_cached_instance = do_cache_instance
        return self
    def __init__(self, *, optimize_do_blanking: bool = True, try_reduce_objects: bool = False, **kwargs):
        if getattr(self, '_is_initted', False): return
        self.optimize_do_blanking = optimize_do_blanking
        self.try_reduce_objects = try_reduce_objects
        for k,v in kwargs.items():
            setattr(self, k, v)
        self._size_base = 225 - len(self.TYPE_KEYS) # we need to reserve len(self.TYPE_KEYS) bytes to encode type-keys
        self._type_to_pfx = {t: bytes((self._size_base + n,)) for n,t in enumerate(self.TYPE_KEYS)}
        self._pfx_to_type = {p: t for t,p in self._type_to_pfx.items()}
        self._is_initted = True
    def __setattr__(self, attr: str, val: typing.Any):
        if getattr(self, '_is_cached_instance', False) and getattr(self, '_is_initted', False):
            raise TypeError('Cannot set attributes on cached instances.'
                            'Either create a new instance and set attributes in its kwargs,'
                            'or disable caching (do_cache_instance=False) if you must modify an existing instance')
        super().__setattr__(attr, val)

    def encode_size(self, s: int) -> bytes:
        '''Encodes an integer in self._size_base; originally inspired by https://stackoverflow.com/a/28666223'''
        if not s: return b''
        return bytes(((s % (self._size_base**p))) // (self._size_base**(p-1)) for p in range(1, math.ceil(1+math.log(s+1, self._size_base))))[::-1]
    def decode_size(self, bs: bytes) -> int:
        '''
            Decodes an integer from self._size_base
            Not that this not used by the current implementation of siunarchive()
        '''
        if not bs: return 0
        return sum(d*(self._size_base**p) for p,d in enumerate(reversed(bs)))

    def _try_encode_literal(self, l: object) -> str | None:
        r = repr(l)
        try: e = literal_eval(r)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError): return None
        if l == e: return None
    def encode(self, o: object) -> tuple[typing.Literal[*TYPE_KEYS], bytes]:
        '''Returns an object's type-key and encoded bytes'''
        match o:
            # Numerics
            case bool():
                return (bool(o), b''),
            case int():
                return (int, o.to_bytes(((o.bit_length() + 1) + 7) // 8, signed=True) \
                        if (o or not self.optimize_do_blanking) else b'')
            case float():
                if self.optimize_do_blanking and not o: return (float, b'')
                return self._encode_to_struct_or_repr(self.S_DOUBLE, float, (o,))
            case complex():
                if self.optimize_do_blanking and not o: return (complex, b'')
                return self._encode_to_struct_or_repr(self.S_COMPLEX, complex, (o.real, o.imag))
            # Sequences
            ## Simple
            case bytes() | bytearray():
                return (bytes, bytes(o))
            case str():
                return (str, o.encode(self.STR_ENCODING))
            ## Recursive
            case tuple() | list():
                return (tuple, self.pack(*(so for so in o)))
            case frozenset() | set():
                return (frozenset, self.pack(*(so for so in o)))
            case dict():
                return (dict, self.pack(*sum(tuple(o.items()), start=())))
            # Others
            case (None):
                return (None, b'')
            case _ if (r := self._try_encode_literal(o)) is not None: # object equals its repr ((sometimes) literal) form
                return (repr, r.encode(self.STR_ENCODING))
        # Try to reduce objects
        if self.try_reduce_objects:
            # Reduce dataclasses
            if dataclasses.is_dataclass(o):
                return self.encode(dataclasses.asdict(o))
            # Reduce arbitrary objects __dict__ and __slots__
            if hasattr(o, '__dict__') or hasattr(o, '__slots__'):
                return self.encode({a: getattr(o, a) for a in
                                    (getattr(o, '__dict__', {}).keys() | set(getattr(o, '__slots__', ())))
                                    if (not a.startswith('_')) and hasattr(o, a)})
        # Fail
        raise TypeError(f'Cannot encode object {o!r} of type {type(o).__qualname__}')
    def sarchive(self, stream: io.BytesIO, data: tuple[tuple[typing.Literal[*TYPE_KEYS], bytes], ...]):
        '''Archives sets of encoded data into a stream'''
        for t,d in data:
            stream.write(self.encode_size(len(d)))
            stream.write(self._type_to_pfx[t])
            stream.write(d)
    def archive(self, data: tuple[tuple[typing.Literal[*TYPE_KEYS], bytes], ...]) -> bytes:
        '''Archives sets of encoded data into bytes'''
        with io.BytesIO() as stream:
            self.sarchive(stream, data)
            return stream.getvalue()
    def spack(self, stream: io.BytesIO, *objects: object) -> bytes:
        '''Packs a sequence of objects into a stream'''
        self.sarchive(stream, (self.encode(o) for o in objects))
    def pack(self, *objects: object) -> bytes:
        '''Packs a sequence of objects into bytes'''
        with io.BytesIO() as stream:
            self.spack(stream, *objects)
            return stream.getvalue()

    def decode(self, t: typing.Literal[*TYPE_KEYS], e: bytes) -> object:
        '''Decodes encoded data, given its pack-type'''
        if not e:
            if isinstance(t, type): return t()
            elif t == repr: raise TypeError(f'Cannot decode zero-length repr at {e!r}')
            else: return t
        # Numerics
        if t is True: return True
        if t is False: return False
        if t is int: return int.from_bytes(e)
        if t is float:
            return self.S_DOUBLE.unpack(e)
        if t is complex:
            return complex(*self.S_COMPLEX.unpack(e))
        # Sequences
        ## Simple
        if t is bytes: return e
        if t is str:
            return e.decode(self.STR_ENCODING)
        ## Recursive
        if t is tuple:
            return tuple(self.decode(rp, re) for rp, re in self.iunarchive(e))
        if t is frozenset:
            return frozenset(self.decode(rp, re) for rp, re in self.iunarchive(e))
        if t is dict:
            seq = self.unpack(e)
            return dict(zip(seq[::2], seq[1::2]))
        # Other
        if t is None: return None
        if t is repr:
            return literal_eval(e.decode(self.STR_ENCODING))
    def sunarchive_one(self, stream: io.BytesIO) -> tuple[typing.Literal[*TYPE_KEYS], bytes] | None:
        '''Un-archives a single sequence of data from a stream'''
        p = size = 0
        while True:
            b = stream.read(1)
            if not b: return None
            if b[0] >= self._size_base: break
            size += self._size_base**p*b[0]
            p += 1
        return (self._pfx_to_type[b], stream.read(size))
    def siunarchive(self, stream: io.BytesIO) -> typing.Generator[tuple[typing.Literal[*TYPE_KEYS], bytes], None, None]:
        '''Un-archives and yields sequences of data from a stream'''
        while (seq := self.sunarchive_one(stream)) is not None: yield seq
    def iunarchive(self, arch: bytes) -> typing.Generator[tuple[typing.Literal[*TYPE_KEYS], bytes], None, None]:
        '''Un-archives and yields sequences of data from bytes'''
        with io.BytesIO(arch) as stream:
            yield from self.siunarchive(stream)
    def unarchive(self, arch: bytes) -> tuple[tuple[typing.Literal[*TYPE_KEYS], bytes]]:
        '''Un-archives sequences of data from bytes'''
        return tuple(self.iunarchive(arch))
    def siunpack(self, stream: io.BytesIO) -> typing.Iterator[object]:
        '''Returns an iterator that unpacks objects from a stream'''
        return (self.decode(t, a) for t,a in self.siunarchive(stream))
    def iunpack(self, packed: bytes) -> typing.Generator[object, None, None]:
        '''Returns an iterator that unpacks objects from bytes'''
        with io.BytesIO(packed) as stream:
            yield from self.siunpack(stream)
    def unpack(self, packed: bytes) -> tuple[object, ...]:
        '''
            Unpacks and returns a tuple of objects from bytes
            Convenience method for `tuple(iunpack(packed))`
            Note that pack() and unpack() are sequence-based, therefore:
                `object == unpack(pack(object))[0]`
                and `(object1, object2) == unpack(pack(object1, object2))`
                (assuming that packing succeeds and that `try_reduce_objects` is disabled)
        '''
        return tuple(self.iunpack(packed))

packer = Packer()

def pack(*objects: object, **packer_attrs) -> bytes:
    '''
        Packs a series of objects into bytes
        If packer_attrs is supplied, then a new Packer is created with every call
            if you need to repeatedly use custom Packer attributes, then create your own Packer instance*
                *unless you are willing to rely on weakref instance caching (`do_cache_instance=True`), which is enabled by default
    '''
    return (Packer(**packer_attrs) if packer_attrs else packer).pack(*objects)
def unpack(packed: bytes, **packer_attrs) -> tuple[object, ...]:
    '''
        Unpacks a packed series of objects
        If packer_attrs is supplied, then a new Packer is created with every call
            if you need to repeatedly use custom Packer attributes, then create your own Packer instance*
                *unless you are willing to rely on weakref instance caching (`do_cache_instance=True`), which is enabled by default
        Note that pack() and unpack() are sequence-based, therefore:
            `object == unpack(pack(object))[0]`
            and `(object1, object2) == unpack(pack(object1, object2))`
            (assuming that packing succeeds and that `try_reduce_objects` is disabled)
    '''
    return (Packer(**packer_attrs) if packer_attrs else packer).unpack(packed)
