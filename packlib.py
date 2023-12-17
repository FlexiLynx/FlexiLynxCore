#!/bin/python3

#> Imports
import io
import struct
import typing
from ast import literal_eval
#</Imports

#> Header >/
class Packer:
    __slots__ = (
        'optimize_do_blanking',
        'try_reduce_objects',
        '_size_base', '_trans_table',
        '_type_to_pfx', '_pfx_to_type',
        '__dict__', # allow customizing class-vars on instances
    )

    STR_ENCODING = 'UTF-8'

    S_DOUBLE = struct.Struct('!d')
    S_COMPLEX = struct.Struct('!dd')

    PREFIX_DEFS = { #ordered simplest to most complex (sans Other)
        # Numerics [lowercase prefixes]
        False: b'f', True: b't', int: b'i', float: b'd', complex: b'c',
        # Sequences [uppercase prefixes]
        ## Simple sequences (encoded as-is)
        bytes: b'B', str: b'S',
        # sequences
        tuple: b'T', frozenset: b'F', dict: b'D',
        # Other keys [symbols]
        None: b'/', repr: b'#',
    }

    @staticmethod
    def inbase(n: int, base: int) -> bytes:
        '''Converts an integer to an arbitrary base, then converts it to bytes, thanks to https://stackoverflow.com/a/28666223'''
        if not n: return (0,)
        digits = []
        while n:
            digits.append(int(n % base))
            n //= base
        return bytes(digits)
    @staticmethod
    def frombase(b: bytes, base: int) -> int:
        '''Converts an integer from bytes in an arbitrary base, reverse-engineered from https://stackoverflow.com/a/28666223'''
        if not b: return 0
        n = 0
        for p,d in enumerate(b): n += d * (base**p)
        return n

    def __init__(self, optimize_do_blanking: bool = True, try_reduce_objects: bool = False, **kwargs):
        self.optimize_do_blanking = optimize_do_blanking
        try_reduce_objects = try_reduce_objects
        for k,v in kwargs.items():
            setattr(self, k, v)
        self._size_base = 225 - len(self.PREFIX_DEFS) - 1 # we need to reserve len(self.PREFIX_DEFS) + 1 byte-values to encode prefixes and a separator
        self._type_to_pfx = {t: bytes((self._size_base + n,)) for n,t in enumerate(self.PREFIX_DEFS.keys())}
        self._pfx_to_type = {p: t for t,p in self._type_to_pfx.items()}
        # Translation table
        self._trans_table = bytes.maketrans(b''.join(self._type_to_pfx.values()) + b''.join(self.PREFIX_DEFS.values()), b''.join(self.PREFIX_DEFS.values()) + b''.join(self._type_to_pfx.values()))
    # Encode
    ## Forward
    def _encode_to_struct_or_repr(self, p: struct.Struct, t: typing.Literal[*PREFIX_DEFS], o: tuple[object, ...]) -> tuple[struct.Struct | typing.Literal[repr], bytes]:
        ro = repr(o)
        if len(ro) < p.size: return (repr, ro)
        try: so = p.pack(*o)
        except struct.error: pass
        else: return (t, so)
        return (repr, ro)
    def encode(self, o: object) -> tuple[typing.Literal[*PREFIX_DEFS], bytes]:
        '''
            The first step in the packing process
            Encodes an object into bytes and return its packed-type
        '''
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
                return (tuple, self.archive(self.encodes(o)))
            case frozenset() | set():
                return (frozenset, self.archive(self.encodes(o)))
            case dict():
                return (dict, b''.join(self.pack(k,v) for k,v in o.items()))
            # Others
            case (None):
                return (None, b'')
            case _ if repr(o) == ast.literal_eval(r): # object equals its repr ((sometimes) literal) form
                return (repr, r.encode(self.STR_ENCODING))
    def iencodes(self, os: tuple[object, ...]) -> typing.Generator[[tuple[typing.Literal[*PREFIX_DEFS], bytes]], None, None]:
        '''Encodes a series of objects into archivable packed-types and bytes'''
        for o in os:
            enc = self.encode(o)
            if enc[0] is repr:
                yield enc
                continue
            if len(ren := (r := repr(o)).encode(self.STR_ENCODING)) < len(enc[1]):
                try: lit = o == ast.literal_eval(r)
                except ValueError: lit = False
                if lit:
                    yield (repr, ren)
                    continue
            yield enc
    def encodes(self, os: tuple[object, ...]) -> tuple[tuple[typing.Literal[*PREFIX_DEFS], bytes], ...]:
        '''Encodes a series of objects into an archivable series of packed-types and bytes'''
        return tuple(self.iencodes(os))
    ## Reverse
    def decode(self, p: typing.Literal[*PREFIX_DEFS], e: bytes) -> object:
        '''
            The last step in the unpacking process
            Decodes encoded data given its pack-type
        '''
        t = self._pfx_to_type[p]
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
            return tuple(self.decode(rp, re) for rp, re in self.unarchive(e))
        if t is frozenset:
            return frozenset(self.decode(rp, re) for rp, re in self.unarchive(e))
        if t is dict:
            return tuple(self.decode(rp, re) for rp, re in self.unarchive(e))
        # Other
        if t is None: return None
        if t is repr:
            return literal_eval(e.decode(self.STR_ENCODING))
    # Archive
    ## Forward
    def archive_into(self, stream: io.BytesIO, data: tuple[tuple[bytes, bytes], ...]):
        '''
            The final step in the packing process
            Writes a tuple of tuples of packed-types and encoded data in an unpackable form into a stream
        '''
        for p,v in data:
            if v or not self.optimize_do_blanking:
                stream.write(bytes(self.inbase(len(v), self._size_base)))
            stream.write(p)
        stream.write(b'\xFF')
        for _,v in data: stream.write(v)
    def archive(self, data: tuple[tuple[bytes, bytes], ...]) -> bytes:
        '''
            The final step in the packing process
            Archives a tuple of tuples of packed-types and encoded data into an unpackable form
        '''
        with io.BytesIO() as stream:
            self.archive_into(stream, data)
            return stream.getvalue()
    ## Reverse
    def iunarchive_from(self, stream: io.BytesIO) -> typing.Iterator[tuple[bytes, bytes]]:
        '''
            The first step in the unpacking process
            Reads an iterator of tuples of type-prefixes and encoded data from a stream
        '''
        types = []
        with io.BytesIO() as ssize:
            while True:
                n = stream.read(1)
                print(f'{n=!r} {types=!r} {ssize.getvalue()=!r}')
                if n == b'\xFF':
                    print(types)
                    break
                if n[0] >= self._size_base:
                    print(n[0])
                    print(n)
                    print(ssize.getvalue())
                    print('yay')
                    types.append((n, self.frombase(ssize.getvalue(), self._size_base)))
                    ssize.truncate(0); ssize.seek(0, io.SEEK_SET)
                    continue
                ssize.write(n)
        return ((pfx, stream.read(size)) for pfx,size in types)
    def unarchive_from(self, stream: io.BytesIO) -> tuple[tuple[bytes, bytes], ...]:
        '''
            The first step in the unpacking process
            Reads a tuple of tuples of type-prefixes and encoded data from a stream
            Convenience function for `tuple(iunarchive_from(stream))`
        '''
        return tuple(self.iunarchive_from(stream))
    def unarchive(self, archived: bytes) -> tuple[tuple[bytes, bytes], ...]:
        '''
            The first step in the unpacking process
            Reads a tuple of tuples of type-prefixes and encoded data from bytes
        '''
        with io.BytesIO(archived) as stream:
            return tuple(self.iunarchive_from(stream))
    # Translate
    def translate(self, archive: bytes) -> bytes:
        '''Makes archived bytes slightly more human-readable or computer-readable'''
        #return archive.translate(self._trans_table)
        return archive
    # Pack
    def pack(self, *os: object) -> bytes:
        '''Packs a sequence of arbitrary objects into bytes'''
        return self.translate(self.archive(tuple((self._type_to_pfx[t], v) for t,v in self.encodes(os))))
    def iunpack_one(self, b: bytes) -> typing.Iterator[object]:
        '''Unpacks a sequence of packed objects'''
        return (self.decode(t,v) for t,v in self.unarchive(self.translate(b)))
    def iunpack(self, b: bytes) -> typing.Iterator
packer = Packer()
