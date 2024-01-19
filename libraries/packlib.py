#!/bin/python3

#> Imports
import io
import math
import types
import struct
import weakref
import dataclasses
import typing
from enum import IntEnum
from ast import literal_eval
from fractions import Fraction
from collections import abc, namedtuple
#</Imports

#> Header >/
__all__ = ('Packer', 'packer', 'pack', 'unpack', 'ReduceNamedtuple')

ReduceNamedtuple = IntEnum('ReduceNamedtuple', ('FAIL', 'AS_DICT', 'AS_TUPLE', 'AS_NAMEDTUPLE'))

class Packer:
    __slots__ = (
        'optimize_do_blanking',
        'try_reduce_objects',
        'reduce_namedtuple',
        '_size_base',
        '_type_to_pfx', '_pfx_to_type',
        '_is_cached_instance', '_is_initted',
        '__dict__', # allow customizing class-vars on instances
        '__weakref__', # allow instance caching
    )

    STR_ENCODING = 'UTF-8'

    S_DOUBLE = struct.Struct('!d')
    S_COMPLEX = struct.Struct('!dd')

    FRACTION_PRECISION = Fraction.limit_denominator.__defaults__[0]

    TYPE_KEYS = ( # ordered simplest to most complex (sans Other)
        # Numerics
        False, True, int, float, complex, Fraction,
        # Sequences
        ## Simple sequences (encoded as-is)
        bytes, str,
        ## Recursive sequences
        tuple, frozenset, dict, namedtuple,
        # Other keys
        None, repr,
    )

    EXTENDED_CONSTANTS = (None, NotImplemented, Ellipsis)

    _INSTANCE_CACHE = weakref.WeakValueDictionary() # instances have no state, so it's safe to cache them

    def __new__(cls, do_cache_instance: bool = True, **kwargs):
        if do_cache_instance:
            h = hash(tuple(kwargs.items()))
            if (i := cls._INSTANCE_CACHE.get(h, None)) is not None: return i # cache hit
        self = super().__new__(cls)
        if do_cache_instance:
            cls._INSTANCE_CACHE[h] = self # cache miss, save it for next time
        self._is_cached_instance = do_cache_instance
        return self
    def __init__(self, optimize_do_blanking: bool = True, try_reduce_objects: bool = False,
                 reduce_namedtuple: ReduceNamedtuple = ReduceNamedtuple.AS_NAMEDTUPLE, **kwargs):
        if getattr(self, '_is_initted', False): return
        self.optimize_do_blanking = optimize_do_blanking
        self.try_reduce_objects = try_reduce_objects
        self.reduce_namedtuple = reduce_namedtuple
        for k,v in kwargs.items():
            setattr(self, k, v)
        self._size_base = 255 - len(self.TYPE_KEYS) # we need to reserve len(self.TYPE_KEYS) bytes to encode type-keys
        self._type_to_pfx = {t: bytes((self._size_base + n,)) for n,t in enumerate(self.TYPE_KEYS)}
        self._pfx_to_type = {p: t for t,p in self._type_to_pfx.items()}
        self._is_initted = True
    def __setattr__(self, attr: str, val: typing.Any):
        if getattr(self, '_is_cached_instance', False) and getattr(self, '_is_initted', False):
            raise TypeError('Cannot set attributes on cached instances. '
                            'Either create a new instance and set attributes in its kwargs, '
                            'or disable caching (do_cache_instance=False) if you must modify an existing instance')
        super().__setattr__(attr, val)

    @staticmethod
    def _i_to_base(n: int, base: int) -> bytes:
        return bytes(((n % (base**p))) // (base**(p-1)) for p in range(1, math.ceil(1+math.log(n+1, base))))
    @staticmethod
    def _i_from_base(bn: bytes, base: int) -> int:
        if not bn: return 0
        return sum(d*(base**p) for p,d in enumerate(bn))
    def encode_size(self, s: int) -> bytes:
        '''Encodes an integer in self._size_base; originally inspired by https://stackoverflow.com/a/28666223'''
        if not s: return b''
        return self._i_to_base(s, self._size_base)
    def decode_size(self, bs: bytes) -> int:
        '''
            Decodes an integer from self._size_base
            Not that this not used by the current implementation of siunarchive()
        '''
        return _i_from_base(bs, self._size_base)

    def _try_encode_literal(self, l: object) -> str | None:
        r = repr(l)
        try: e = literal_eval(r)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError): return None
        if l == e: return r
        return None
    def encode(self, o: object) -> tuple[typing.Literal[*TYPE_KEYS], bytes]:
        '''Returns an object's type-key and encoded bytes'''
        match o:
            # Numerics
            case bool():
                return (bool(o), b'')
            case int():
                return (int, o.to_bytes(((o.bit_length() + 1) + 7) // 8, signed=True) \
                        if (o or not self.optimize_do_blanking) else b'')
            case float():
                if self.optimize_do_blanking and not o: return (float, b'')
                fenc = self.encode(Fraction(o))[1]
                if len(fenc) < self.S_DOUBLE.size: return (float, fenc)
                try: return (float, self.S_DOUBLE.pack(o))
                except struct.error: return fenc
            case complex():
                if self.optimize_do_blanking and not o: return (complex, b'')
                pak = self.pack(o.real, o.imag)
                if len(pak) < self.S_COMPLEX.size: return (complex, pak)
                try:
                    return (complex, self.S_COMPLEX.pack(o.real, o.imag))
                except struct.error: return (complex, pak)
            case Fraction():
                n,d = o.limit_denominator(self.FRACTION_PRECISION).as_integer_ratio()
                np = n.to_bytes(((n.bit_length() + 1) + 7) // 8, signed=True) \
                     if (n or not self.optimize_do_blanking) else b'' # numerator is signed
                dp = self._i_to_base(d, 254) if (d or not self.optimize_do_blanking) else b'' # denominator is not
                return (Fraction, np + b'\xFF' + dp)
            # Sequences
            ## Simple
            case bytes() | bytearray():
                return (bytes, bytes(o))
            case str():
                return (str, o.encode(self.STR_ENCODING))
            ## Recursive
            case abc.Sequence():
                if hasattr(o, '_asdict') and (self.reduce_namedtuple != ReduceNamedtuple.AS_TUPLE):
                    # if it's a namedtuple and we don't treat namedtuples as regular tuples
                    if self.reduce_namedtuple == ReduceNamedtuple.FAIL:
                        raise TypeError('Cannot reduce namedtuples (reduce_namedtuple is FAIL)')
                    if self.reduce_namedtuple == ReduceNamedtuple.AS_DICT: # render as dict
                        return self.encode(o._asdict())
                    if self.reduce_namedtuple == ReduceNamedtuple.AS_NAMEDTUPLE:
                        return (namedtuple, self.pack(o.__class__.__name__, o.__module__, *sum(tuple(o._asdict().items()), start=())))
                    raise ValueError(f'reduce_namedtuple is an illegal value: {self.reduce_namedtuple!r}')
                return (tuple, self.pack(*(so for so in o)))
            case abc.Set():
                return (frozenset, self.pack(*(so for so in o)))
            case abc.Mapping():
                return (dict, self.pack(*sum(tuple(o.items()), start=())))
            # Others
            case _ if (o in self.EXTENDED_CONSTANTS):
                return (None, b'' if (self.optimize_do_blanking and o is None) else bytes((self.EXTENDED_CONSTANTS.index(o),)))
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
    def encode_many(self, objects: tuple[object, ...]) -> typing.Iterator[tuple[typing.Literal[*TYPE_KEYS], bytes]]:
        '''Encode a set of objects, both with `encode()` and as literals, then yield the shortest viable representation'''
        for o in objects:
            et,ev = self.encode(o)
            if ((lit := self._try_encode_literal(o)) is not None) \
               and (len(lit) < len(ev)): yield (repr, lit.encode(self.STR_ENCODING))
            else: yield (et, ev)
    def sarchive(self, stream: typing.BinaryIO, data: tuple[tuple[typing.Literal[*TYPE_KEYS], bytes], ...]):
        '''Archives sets of encoded data into a stream'''
        data = tuple(data)
        for t,d in data:
            stream.write(self.encode_size(len(d)))
            stream.write(self._type_to_pfx[t])
            stream.write(d)
    def archive(self, data: tuple[tuple[typing.Literal[*TYPE_KEYS], bytes], ...]) -> bytes:
        '''Archives sets of encoded data into bytes'''
        with io.BytesIO() as stream:
            self.sarchive(stream, data)
            return stream.getvalue()
    def spack(self, stream: typing.BinaryIO, *objects: object) -> bytes:
        '''Packs a sequence of objects into a stream'''
        self.sarchive(stream, self.encode_many(objects))
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
        if t is int: return int.from_bytes(e, signed=True)
        if t is float:
            if len(e) == self.S_DOUBLE.size:
                return self.S_DOUBLE.unpack(e)[0]
            return float(self.decode(Fraction, e))
        if t is complex:
            if len(e) == self.S_COMPLEX.size:
                return self.S_COMPLEX.unpack(e)
            return complex(*self.unpack(e))
        if t is Fraction:
            n,d = e.rsplit(b'\xFF', 1)
            return Fraction(int.from_bytes(n, signed=True), self._i_from_base(d, 254))
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
        if t is namedtuple:
            seq = self.unpack(e)
            dic = dict(zip(seq[2::2], seq[3::2]))
            return namedtuple(seq[0], dic.keys(), module=seq[1])(**dic)
        # Other
        if t is None:
            if len(e) != 1:
                raise ValueError(f'Invalid extended constant value {e!r} (must have a length of 1 or 0')
            return self.EXTENDED_CONSTANTS[e[0]]
        if t is repr:
            return literal_eval(e.decode(self.STR_ENCODING))
    def sunarchive_one(self, stream: typing.BinaryIO) -> tuple[typing.Literal[*TYPE_KEYS], bytes] | None:
        '''Un-archives a single sequence of data from a stream'''
        p = size = 0
        while True:
            b = stream.read(1)
            if not len(b): return None
            if b[0] >= self._size_base: break
            size += self._size_base**p*b[0]
            p += 1
        return (self._pfx_to_type[b], stream.read(size))
    def siunarchive(self, stream: typing.BinaryIO) -> typing.Generator[tuple[typing.Literal[*TYPE_KEYS], bytes], None, None]:
        '''Un-archives and yields sequences of data from a stream'''
        while (seq := self.sunarchive_one(stream)) is not None: yield seq
    def iunarchive(self, arch: bytes) -> typing.Generator[tuple[typing.Literal[*TYPE_KEYS], bytes], None, None]:
        '''Un-archives and yields sequences of data from bytes'''
        with io.BytesIO(arch) as stream:
            yield from self.siunarchive(stream)
    def unarchive(self, arch: bytes) -> tuple[tuple[typing.Literal[*TYPE_KEYS], bytes]]:
        '''Un-archives sequences of data from bytes'''
        return tuple(self.iunarchive(arch))
    def siunpack(self, stream: typing.BinaryIO) -> typing.Iterator[object]:
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

def inspect(packed: bytes, packer: Packer = packer, *,
            fmtk: str = 'hex', input: typing.Callable[[str], str] = input, print: typing.Callable[[str], None] = print) -> bool:
    '''Writes out details about the packed bytes and allows interactive inspection and recursion'''
    import base64, traceback
    fmts = {
        'repr': repr,
        'hex': bytes.hex,
        'b85': lambda b: base64.b85encode(b).decode(),
        'replace': lambda b: b.decode(errors='replace'),
        '\\': lambda b: b.decode(errors='backslashreplace'),
    }; fmt = fmts[fmtk]
    def p_cmds():
        print('Commands:\n'
              '- "q": quit\n'
              '- "b": same as quit, but only quits the current `inspect`, not all previous ones ("b"acks out of recursion)\n'
              '- "p": prints the list of entries\n'
              '- "r": prints the entirety of the raw bytes that are being inspected\n'
              '- "i <i>": recursively inspect bytes from entry "<i>"\n'
              '- "d [i]": decode (possibly recursively) entry "[i]" (if "[i]" is not given, unpack the entirety of the currently inspected bytes)\n'
              '- "f [n]": change format to format "[n]"; if "[n]" is not given, then print a list of available formats')
    entries = []
    def p_meta(e: int):
        s = packer.encode_size(len(entries[e][1]))
        t = packer._type_to_pfx[entries[e][0]]
        print(f'Entry {str(e+1).rjust(2, "0")}: {fmt(s + t + entries[e][1])}\n'
              f' size: {fmt(s)} -> {len(entries[e][1])}\n'
              f' type: {fmt(t)} -> {getattr(entries[e][0], "__name__", repr(entries[e][0]))}')
    last = 0
    pakd = io.BytesIO(packed)
    while True:
        entries.append(packer.sunarchive_one(pakd))
        if entries[-1] is None:
            entries.pop(); break
        print(f'--Decoded {fmt(packed[last:pakd.tell()])}--')
        p_meta(len(entries)-1)
        last = pakd.tell()
    if not entries:
        print('No entries; backing out')
        return True
    p_cmds()
    while True:
        c = input('Enter command >').lower().split(' ')
        match c:
            case ('q',):
                print('Quitting')
                return False
            case ('b',):
                print('Backing out')
                return True
            case ('p',):
                for i in range(len(entries)): p_meta(i)
            case ('r',): print(fmt(packed))
            case ('i', i):
                if not i.isdigit(): print(f'Not a number: {i!r}')
                if not inspect(entries[int(i)-1][1], fmtk=fmtk, input=input, print=print):
                    return False
            case ('d',):
                print(repr(packer.unpack(packed)))
            case ('d', i):
                if not i.isdigit(): print(f'Not a number: {i!r}')
                elif 0 < int(i) <= len(entries):
                    print(repr(packer.decode(*entries[int(i)-1])))
                else: print(f'Out of bounds: {i}')
            case ('f',): print(', '.join(fmts.keys()))
            case ('f', f):
                if f in fmts:
                    fmtk = f
                    fmt = fmts[fmtk]
                else: print(f'Format {f!r} not recognized')
            case _:
                print(f'Unrecognized command {c}')
                p_cmds()

# Self-test
def _stage_selftest():
    # Imports
    import random, string, math, itertools
    # Structure generation
    global _test_singlegen
    global _test_nestedgen
    global _test_struct_size
    global _test_genstruct
    global _test_genstruct_s
    _test_singlegen = (
        lambda ml, db: ''.join(random.choices(string.printable, k=random.randint(0, ml))), # str
        lambda ml, db: random.randbytes(random.randint(0, ml)), # bytes
        lambda ml, db: bool(random.randint(0, 1)), # bool
        lambda ml, db: random.randint(0, ml), # int
        lambda ml, db: random.randint(0, ml) / random.randint(1, ml+1), # float
        lambda ml, db: complex(random.randint(0, ml) / random.randint(1, ml+1), random.randint(0, ml) / random.randint(1, ml+1)), # complex
        lambda ml, db: None, # None
    )
    _test_nestedgen = (
        lambda ml, db: {random.choice(_test_singlegen)(ml, db-1): _test_genstruct(ml, db-1) for _ in range(random.randint(0, ml))}, # dict
        lambda ml, db: tuple(_test_genstruct(ml, db-1) for _ in range(random.randint(0, ml))), # tuple
        lambda ml, db: frozenset(random.choice(_test_singlegen)(ml, db-1) for _ in range(random.randint(0, ml))), # set
    )
    _test_struct_size = (10, 0.5)
    _test_genstruct = lambda maxlen, depthbias: random.choice(_test_singlegen+(_test_nestedgen*depthbias))(maxlen, depthbias)
    _test_genstruct_s = lambda s: _test_genstruct(math.ceil(_test_struct_size[0]*s), math.ceil(_test_struct_size[1]*s))
    # Single-testing methods
    global _test_tests_1
    global _test_test_s1
    global _test_tests_2
    global _test_test_s2
    global _test_TEST_NO_BLANKING
    _test_TEST_NO_BLANKING = False
    _test_tests_1 = {
        'pack(obj) == pack(obj)': lambda s: pack(s) == pack(s),
        'obj == unpack(pack(obj))[0]': lambda s: s == unpack(pack(s))[0],
    }
    _test_tests_2 = {
        'pack(obj1, obj2) == pack(obj1)+pack(obj2)': lambda s1, s2: pack(s1, s2) == pack(s1)+pack(s2),
        '(obj1, obj2) == unpack(pack(obj1, obj2))': lambda s1, s2: (s1, s2) == unpack(pack(s1, s2)),
        '(obj1, obj2) == unpack(pack(obj1)+pack(obj2))': lambda s1, s2: (s1, s2) == unpack(pack(s1)+pack(s2)),
    }
    _test_test_s1 = 'obj == unpack(pack(obj))[0]'
    _test_test_s2 = '(obj1, obj2) == unpack(pack(obj1, obj2))'
    # Big test
    global _test_testall
    def _test_testall(poolsize: int, struct_size: int = 4, struct_pool_notify_every_perc: int = 10, do_output: bool = False,
                      skip_some: bool = False, skip_1: bool = False, skip_2: bool = False) -> tuple[dict, dict] | None:
        # Calculate sizings
        ml = math.ceil(_test_struct_size[0]*struct_size)
        db = math.ceil(_test_struct_size[1]*struct_size)
        # Generate structures
        print(f'Generating {poolsize} structures with size of {struct_size} (max length: {ml}; depth bias: {db}')
        print('This could take a while, depending on the size of the pool and the size of the structures')
        pool = tuple(_test_genstruct(ml, db) for n in range(poolsize) \
                     if (((n+1) % ((poolsize//struct_pool_notify_every_perc) or 1)) or print(f'Generating structure {n+1} of {poolsize}'),)) # if True, just prints out every struct_pool_notify_every'th run
        # Generate combinations
        print(f'Generating 2-combinations for {len(pool)} structures...')
        if skip_2:
            print('Not generating combinations (skip_2=True)')
            combos = ()
        else: combos = tuple(itertools.combinations(pool, 2))
        print(f'Generated {len(combos)} 2-combinations of {len(pool)} structures')
        # Expose debugging globals
        global _test_last_test
        global _test_last_vals
        # Run single-tests
        print(f'Running 1-tests; ({len(pool)} tests each...')
        runs_1 = {}
        if skip_1:
            print('Skipping 1-tests (skip_1=True)')
        else:
            for n,tf in ((_test_test_s1, _test_tests_1[_test_test_s1]),) if skip_some else _test_tests_1.items():
                runs_1[n] = []
                print(f'Running {n} {len(pool)} times...')
                for s in pool:
                    _test_last_test = n
                    _test_last_vals = (s,)
                    runs_1[n].append({
                        'structure': s,
                        'passed': tf(s),
                    })
                print(f'Successful runs: {len(tuple(r for r in runs_1[n] if r["passed"]))} / {len(pool)}')
        # Run double-tests
        print(f'Running 2-tests; ({len(combos)} tests each...')
        runs_2 = {}
        if skip_2:
            print('Skipping 2-tests (skip_2=True)')
        else:
            for n,tf in ((_test_test_s2, _test_tests_2[_test_test_s2]),) if skip_some else _test_tests_1.items():
                runs_2[n] = []
                print(f'Running {n} {len(combos)} times...')
                for s1,s2 in combos:
                    _test_last_test = n
                    _test_last_vals = (s1, s2)
                    runs_2[n].append({
                        'structure1': s1,
                        'structure2': s2,
                        'passed': tf(s1, s2),
                    })
                print(f'Successful runs: {len(tuple(r for r in runs_2[n] if r["passed"]))} / {len(combos)}')
        if do_output: return runs_1, runs_2
        return None # interactive test results take up a lot of space that takes a long time to print in IDLE
