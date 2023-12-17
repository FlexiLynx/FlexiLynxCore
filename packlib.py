#!/bin/python3

#> Imports
import io
import struct
import typing
import functools
from collections import UserDict
from ast import literal_eval
#</Imports

#> Header >/
__all__ = ('pack', 'unpack', 'iunpack', 'sunpack')

class Packer:
    __slots__ = ()

    HEADER = b'\x01Lpak\xFF'
    STR_ENCODING = 'UTF-8'

    PACK_FAILED = object()

    #FLOAT = struct.Struct('!f') # note: floats lose too much precision
    DOUBLE = struct.Struct('!d')
    #COMPLEX_FLOAT = struct.Struct('!ff')
    COMPLEX_DOUBLE = struct.Struct('!dd')

    # prefixes must not be numbers (0-9), as these are used to encode sizes
    type_to_prefix = {
        # Types
        ## Sequences
        str: b's',
        bytes: b'b',
        tuple: b't',
        frozenset: b'S',
        dict: b'D',
        ## Numerics
        bool: b'B',
        int: b'i',
        #FLOAT: b'f',
        DOUBLE: b'F',
        #COMPLEX_FLOAT: b'c',
        COMPLEX_DOUBLE: b'C',
        # Other
        None: b'N',
        repr: b'@',
        PACK_FAILED: b'!',
        # Reduction
        #type: b'{',
        #object: b'}',
    }; prefix_to_type = {v: k for k,v in type_to_prefix.items() if not isinstance(k, str)}

    def __init__(self):
        assert not (set(b''.join(self.prefix_to_type.keys())) & set('0123456789'.encode(self.STR_ENCODING))), \
               'Prefixes cannot include numeric values'

    #def reduce_type(self, t: type, *, optimize_do_blanking: bool = True) -> bytes:
    #    '''Reduce and encode a type to its name and attributes'''
    #    return self.pack(t.__name__) + b''.join(
    #        self.pack(a, getattr(t, a), optimize_do_blanking=optimize_do_blanking, try_reduce_object=True, fail_on_unknown=False)
    #        for a in dir(t) if hasattr(t, a)
    #            and (self.encode(getattr(t, a), optimize_do_blanking=optimize_do_blanking, try_reduce_object=True, fail_on_unknown=False)[0] is not self.PACK_FAILED))
    def reduce(self, o: object) -> dict[str, object]:
        '''Reduce and encode an object to its attributes'''
        return {a: getattr(o, a) for a in dir(o) if hasattr(o, a) and not a.startswith('_')}
        #return getattr(o, '__dict__', {}) | {a: getattr(o, a) for a in getattr(o, '__slots__', ()) if hasattr(o, a)}
    def encode(self, o: object, *, optimize_do_blanking: bool = True, try_reduce_object: bool = False, fail_on_unknown: bool = True) -> tuple[typing.Literal[*type_to_prefix.keys()], bytes]:
        '''
            Encode an object into a prefix-class and series of bytes
            Recursively calls ) when needed, crashes with circular references
        '''
        #print(self, o, optimize_do_blanking, try_reduce_object, fail_on_unknown)
        repack = functools.partial(self.pack, optimize_do_blanking=optimize_do_blanking, try_reduce_object=try_reduce_object, fail_on_unknown=fail_on_unknown)
        match o:
            # Sequences
            case str():
                return (str, o.encode(self.STR_ENCODING))
            case bytes() | bytearray():
                return (bytes, bytes(o))
            case tuple() | list():
                return (tuple, b''.join(repack(v) for v in o))
            case frozenset() | set():
                return (frozenset, b''.join(repack(v) for v in o))
            case dict():
                return (dict, b''.join(repack(k, v) for k,v in o.items()))
            # Numerics
            case bool():
                return (bool, b'\x01' if o else b'')
            case int():
                return (int, o.to_bytes(((o.bit_length() + 1) + 7) // 8, signed=True) \
                             if (o or not optimize_do_blanking) else b'')
            case float():
                if not o: return (self.DOUBLE, b'')
                rfloat = repr(o).encode(self.STR_ENCODING)
                #if len(rfloat) < self.FLOAT.size:
                #    return (repr, rfloat)
                #try: sfloat = self.FLOAT.pack(o)
                #except struct.error: pass
                #else: return (self.FLOAT, sfloat)
                if len(rfloat) < self.DOUBLE.size:
                    return (repr, rfloat)
                try: sfloat = self.DOUBLE.pack(o)
                except struct.error: pass
                else: return (self.DOUBLE, sfloat)
                return (repr, rfloat)
            case complex():
                if not o: return (self.COMPLEX_DOUBLE, b'')
                rcomp = repr(o).encode(self.STR_ENCODING)
                #if len(rcomp) < self.COMPLEX_FLOAT.size:
                #    return (repr, rcomp)
                #try: scomp = self.COMPLEX_FLOAT.pack(o.real, o.imag)
                #except struct.error: pass
                #else: return (self.COMPLEX_FLOAT, scomp)
                if len(rcomp) < self.COMPLEX_DOUBLE.size:
                    return (repr, rcomp)
                try: scomp = self.COMPLEX_DOUBLE.pack(o.real, o.imag)
                except struct.error: pass
                else: return (self.COMPLEX_DOUBLE, scomp)
                return (repr, rcomp)
            # Other
            case (None):
                return (None, b'')
            # Reduction
            #case type():
            #    if not try_reduce_object:
            #        if not fail_on_unknown: return (self.PACK_FAILED, b'')
            #        raise TypeError('Cannot reduce "type" when try_reduce_object is false')
            #    return (type, self.reduce_type(o, optimize_do_blanking=optimize_do_blanking))
            case object() if try_reduce_object:
                return self.encode(self.reduce(o))
        # Raise/return failures
        if not fail_on_unknown: return (self.PACK_FAILED, b'')
        raise TypeError(f'Cannot reduce {o!r} (type {type(o).__name__}!r)')
    def pack_one(self, o: object, *, optimize_do_blanking: bool = True, try_reduce_object: bool = False, fail_on_unknown: bool = True) -> bytes:
        '''Packs a single object into a serialized, concatable form'''
        pc, pk = self.encode(o, optimize_do_blanking=optimize_do_blanking, try_reduce_object=try_reduce_object, fail_on_unknown=fail_on_unknown)
        if (not pk) and optimize_do_blanking: return self.type_to_prefix[pc] # return bare prefix with no value or length when blanking
        return str(len(pk)).encode(self.STR_ENCODING) + self.type_to_prefix[pc] + pk
    def pack(self, *os: object, optimize_do_blanking: bool = True, try_reduce_object: bool = False, fail_on_unknown: bool = True) -> bytes:
        '''
            Packs multiple objects together
            Note that `pack(obj1, obj2) == pack(obj1)+pack(obj2)`
                  and `pack(obj1, obj2) == pack_one(obj1)+pack_one(obj2)`
        '''
        return b''.join(self.pack_one(o, optimize_do_blanking=optimize_do_blanking, try_reduce_object=try_reduce_object, fail_on_unknown=fail_on_unknown) for o in os)

    #def unreduce_type(self, b: bytes) -> type:
    #    type_, *attrs = self.unpack(b)
    #    return type(type_, (), dict(zip(attrs[::2], attrs[1::2])))
    def unpack_one(self, t: bytes, o: bytes) -> object:
        '''
            Unpacks a single object, given its type and value
            Recursively calls `unpack()` when needed
        '''
        if not o:
            if t == b'N': return None
            if t == b'!': return self.PACK_FAILED
            if t == b'@': raise TypeError(f'Cannot have zero-value packed repr')
            if t in {b'f', b'F'}: return float()
            if t in {b'c', b'C'}: return complex()
            return self.prefix_to_type[t]()
        match t:
            # Sequences
            case b's':
                return o.decode(self.STR_ENCODING)
            case b'b': return o
            case b't':
                return tuple(self.unpack(o))
            case b'S':
                return frozenset(self.unpack(o))
            case b'D':
                seq = self.unpack(o)
                return dict(zip(seq[::2], seq[1::2]))
            # Numerics
            case b'B':
                return bool.from_bytes(o)
            case b'i':
                return int.from_bytes(o, signed=True)
            #case b'f':
            #    return self.FLOAT.unpack(o)[0]
            case b'F':
                return self.DOUBLE.unpack(o)[0]
            #case b'c':
            #    return complex(*self.COMPLEX_FLOAT.unpack(o))
            case b'C':
                return complex(*self.COMPLEX_DOUBLE.unpack(o))
            # Other
            case b'N':
                return None
            case b'@':
                return literal_eval(o.decode(self.STR_ENCODING))
            case b'!':
                return self.PACK_FAILED
            # Reduced
            #case b'{':
            #    return self.unreduce_type(o)
            #case b'}':
            #    return self.unreduce_object(o)
    def sunpack(self, stream: io.BytesIO) -> object:
        '''Unpacks a single object from a stream'''
        size = bytearray()
        while True:
            b = stream.read(1)
            if not b.isdigit(): break
            size.extend(b)
        size = int(size) if size else 0
        if not b: raise EOFError
        return self.unpack_one(b, stream.read(size))
    def iunpack(self, pkd: bytes) -> typing.Generator[object, None, None]:
        '''Unpacks and yields a series of objects'''
        stream = io.BytesIO(pkd)
        while stream.tell() < len(pkd):
            yield self.sunpack(stream)
    def unpack(self, pkd: bytes) -> tuple[object, ...]:
        '''
            Unpacks a series of objects
                Convenience method for `tuple(iunpack(pkd))`
            Note that even a single packed object is considered a series, so:
                `obj == unpack(pack(obj))[0]`
                `(obj1, obj2) == unpack(pack(obj1)+pack(obj2))`
        '''
        return tuple(self.iunpack(pkd))
packer = Packer()

# Extract methods to module namespace
globals().update({a: c for a,c in ((a, getattr(packer, a)) for a in dir(packer) if a.islower()) if callable(c)})

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
    global _test_tests_2
    global _test_TEST_NO_BLANKING
    _test_TEST_NO_BLANKING = False
    _test_tests_1 = {
        'unpack_one(encode(...))': lambda s: s == unpack_one(packer.type_to_prefix[(p := encode(s, optimize_do_blanking=_test_TEST_NO_BLANKING))[0]], p[1]),
        'pack(obj) == pack_one(obj)': lambda s: pack(s, optimize_do_blanking=_test_TEST_NO_BLANKING) == pack_one(s, optimize_do_blanking=_test_TEST_NO_BLANKING),
        'obj == unpack(pack(obj))[0]': lambda s: s == unpack(pack(s, optimize_do_blanking=_test_TEST_NO_BLANKING))[0],
    }
    _test_tests_2 = {
        'pack(obj1, obj2) == pack(obj1)+pack(obj2)': lambda s1, s2: pack(s1, s2, optimize_do_blanking=_test_TEST_NO_BLANKING) == pack(s1, optimize_do_blanking=_test_TEST_NO_BLANKING)+pack(s2, optimize_do_blanking=_test_TEST_NO_BLANKING),
        'pack(obj1, obj2) == pack_one(obj1)+pack_one(obj2)': lambda s1, s2: pack(s1, s2, optimize_do_blanking=_test_TEST_NO_BLANKING) == pack_one(s1, optimize_do_blanking=_test_TEST_NO_BLANKING)+pack_one(s2, optimize_do_blanking=_test_TEST_NO_BLANKING),
        '(obj1, obj2) == unpack(pack(obj1)+pack(obj2))': lambda s1, s2: (s1, s2) == unpack(pack(s1, optimize_do_blanking=_test_TEST_NO_BLANKING)+pack(s2, optimize_do_blanking=_test_TEST_NO_BLANKING)),
    }
    # Big test
    global _test_testall
    def _test_testall(poolsize: int, struct_size: int = 4, struct_pool_notify_every_perc: int = 10, do_output: bool = False) -> tuple[dict, dict] | None:
        ml = math.ceil(_test_struct_size[0]*struct_size)
        db = math.ceil(_test_struct_size[1]*struct_size)
        print(f'Generating {poolsize} structures with size of {struct_size} (max length: {ml}; depth bias: {db}')
        print('This could take a while, depending on the size of the pool and the size of the structures')
        pool = tuple(_test_genstruct(ml, db) for n in range(poolsize) \
                     if (((n+1) % ((poolsize//struct_pool_notify_every_perc) or 1)) or print(f'Generating structure {n+1} of {poolsize}'),)) # if True, just prints out every struct_pool_notify_every'th run
        print(f'Generating 2-combinations for {len(pool)} structures...')
        combos = tuple(itertools.combinations(pool, 2))
        print(f'Generated {len(combos)} 2-combinations of {len(pool)} structures')
        print(f'Running 1-tests; ({len(pool)} tests each...')
        runs_1 = {}
        for n,tf in _test_tests_1.items():
            runs_1[n] = []
            print(f'Running {n} {len(pool)} times...')
            for s in pool:
                runs_1[n].append({
                    'structure': s,
                    'passed': tf(s),
                })
            print(f'Successful runs: {len(tuple(r for r in runs_1[n] if r["passed"]))} / {len(pool)}')
        print(f'Running 2-tests; ({len(combos)} tests each...')
        runs_2 = {}
        for n,tf in _test_tests_2.items():
            runs_2[n] = []
            print(f'Running {n} {len(combos)} times...')
            for s1,s2 in combos:
                runs_2[n].append({
                    'structure1': s1,
                    'structure2': s2,
                    'passed': tf(s1, s2),
                })
            print(f'Successful runs: {len(tuple(r for r in runs_2[n] if r["passed"]))} / {len(combos)}')
        if do_output: return runs_1, runs_2
        return None # interactive test results take up a lot of space that takes a long time to print in IDLE
