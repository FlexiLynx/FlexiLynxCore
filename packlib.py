#!/bin/python3

'''Compress Python builtin objects in a simple, semi-human-readable format that is concatable and writable to files'''

#> Imports
import io
import typing
from ast import literal_eval
#</Imports

#> Header >/
HEADER = b'\x00Lpak\xFF'

# compile mapping
def _obj_to_dict(obj: object) -> dict:
    objd = {}
    if hasattr(obj, '__slots__'):
        objd |= {a: v for a in obj.__slots__}
    if hasattr(obj, '__dict__'):
        objd |= obj.__dict__
    return objd
compiledict = {
    # Sequences
    str: (b's', str.encode),
    bytes: (b'b', lambda b: b),
    bytearray: (b'b', bytes),
    tuple: (b't', lambda t: (b''.join(pack(v, header=False) for v in t))),
    frozenset: (b'S', lambda S: (b''.join(pack(v, header=False) for v in S))),
    dict: (b'D', lambda D: b''.join(pack(k, header=False)+pack(v, header=False) for k,v in D.items())),
    # Numerics
    bool: (b'B', bool.to_bytes),
    int: (b'i', lambda i: i.to_bytes(((i.bit_length() + 1) + 7) // 8, signed=True)),
    float: (b'f', lambda f: repr(f).encode()),
    complex: (b'c', lambda c: repr(c).encode()),
    # None
    type(None): (b'N', lambda n: b''),
    # Special types
    'literalable': (b'@', lambda L: repr(L).encode()),
    'object': (b'D', lambda o: compiledict[dict][1](_obj_to_dict(o))),
}
# mutable to immutable aliases
compiledict[list] = compiledict[tuple]
compiledict[set] = compiledict[frozenset]
# decompile mapping
decompiledict = {
    # Sequences
    b's': bytes.decode,
    b'b': lambda b: b,
    b't': lambda t: unpack(t, header=False),
    b'S': lambda S: frozenset(unpack(S, header=False)),
    b'D': lambda D: dict(zip(*(iter(unpack(D, header=False)),)*2)),
    # Numerics
    b'B': bool.from_bytes,
    b'i': lambda i: int.from_bytes(i, signed=True),
    b'f': lambda f: float(f.decode()),
    b'c': lambda c: complex(c.decode()),
    # None
    b'N': lambda N: None,
    # Special types
    b'@': literal_eval,
}

def pack(data: typing.Union[*(t for t in compiledict.keys() if isinstance(t, type))], header: bool = False) -> bytes:
    '''
        Pack data into a sequence of concatable bytes
            Note: packed data cannot be concatted if it contains a header (except for the first sequence)
            Note: arbitrary objects can be packed from their __dict__ and __slots__ attributes, but upon unpacking they will be reduced to dictionaries
    '''
    datas = []
    # Normal method
    if type(data) in compiledict:
        pfx, fn = compiledict[type(data)]
        datas.append((pfx, fn(data)))
    # Literal method
    pfx, fn = compiledict['literalable']
    try:
        ldat = fn(data)
        if decompiledict[pfx](ldat) != data:
            raise ValueError
    except ValueError: pass
    else: datas.append((pfx, ldat))
    # Object-to-dict method
    if not datas: # almost always going to be larger than other methods
        pfx, fn = compiledict['object']
        datas.append((pfx, fn(data)))
    # Finish packing and return
    if not datas: raise TypeError(f'Cannot pack {data!r} with type {type(data).__qualname__}')
    pfx,cdat = min(datas, key=lambda pd: len(pd[1]))
    return (HEADER if header else b'') + pfx + str(len(cdat)).encode() + bytes(1) + cdat
def iunpack(data: bytes) -> typing.Generator[str | bytes | tuple | frozenset | dict | bool | int | float | type(None), None, None]:
    '''Unpack and yield sequences of packed data'''
    idat = io.BytesIO(data)
    while True:
        t = idat.read(1)
        if t == bytes(): break # end of stream
        if t not in decompiledict:
            raise ValueError(f'Unknown type {t} (dec: {chr(t)!r}) at {len(data)-len(idat)-1}')
        size = bytearray()
        while True:
            s = idat.read(1)
            if s == bytes(1): break #\x00 end-of-length
            size.extend(s)
        size = int(size.decode())
        yield decompiledict[t](idat.read(size))
def unpack(data: bytes, header: typing.Literal['auto'] | bool = 'auto') -> tuple[str | bytes | tuple | frozenset | dict | bool | int | float | type(None), ...]:
    '''
        Unpack an entire sequence of packed sequences of data
            If header is 'auto', then remove the header if it exists
            If header is True, then fail if the header is not present
            If header is False, do nothing about any header
        Whilst arbitrary objects can be packed, note that when unpacked they will be reduced to dictionaries
    '''
    if (header is True) and not data.startswith(HEADER):
        raise TypeError('Rejected data as it does not start with HEADER, perhaps use header=\'auto\'?')
    return tuple(iunpack(data.removeprefix(HEADER) if header in {True, 'auto'} else data))

# testing method
def _make_teststructgen():
    '''Creates a function to generate "testing" structures'''
    import random, string, sys
    _test_singlegen = (
        lambda ml, md: ''.join(random.choices(string.printable, k=random.randint(0, ml))), # str
        lambda ml, md: random.randbytes(random.randint(0, ml)), # bytes
        lambda ml, md: bool(random.randint(0, 1)), # bool
        lambda ml, md: random.randint(0, ml), # int
        lambda ml, md: random.randint(0, ml) / random.randint(1, ml+1), # float
        lambda ml, md: complex(random.randint(0, ml) / random.randint(1, ml+1), random.randint(0, ml) / random.randint(1, ml+1)), # complex
        lambda ml, md: None, # None
    )
    _test_nestedgen = (
        lambda ml, md: {random.choice(_test_singlegen)(ml, md-1): _test_genstruct(ml, md-1) for _ in range(random.randint(0, ml))}, # dict
        lambda ml, md: tuple(_test_genstruct(ml, md-1) for _ in range(random.randint(0, ml))), # tuple
        lambda ml, md: frozenset(random.choice(_test_singlegen)(ml, md-1) for _ in range(random.randint(0, ml))), # set
    )
    _test_genstruct = lambda maxlen, maxdep: random.choice(_test_singlegen+(_test_nestedgen*maxdep*2))(maxlen, maxdep)
    return _test_genstruct
