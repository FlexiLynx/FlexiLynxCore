#!/bin/python3

#> Imports
import re
import base64
import typing

from . import util
#</Imports

#> Header >/
__all__ = ('encode', 'decode', 'chars', 'char_patts', 'char_patt')
def char_patt(chars: str) -> typing.Iterator[str]:
    for seq in (bytes(seq).decode() for seq in util.sequential(map(ord, chars))):
        if not seq: continue
        if len(seq) == 1: yield re.escape(seq[0])
        elif len(seq) == 2: yield re.escape(seq[0])
        else: yield f'{re.escape(seq[0])}-{re.escape(seq[-1])}'
_allbytes = bytes(range(0, 255))
chars = {a[:-6]: ''.join(sorted(map(chr, set(getattr(base64, a)(_allbytes)))))
         for a in dir(base64)
         if len(a) > 6 and a.endswith('encode') and not a[0] == '_'}
char_patts = util.map_vals(lambda c: re.compile(f'[{"".join(char_patt(c))}]'), chars)

def encode(key: typing.Literal[*chars.keys()], val: bytes) -> str:
    return getattr(base64, f'{key}encode')(val).decode()
def decode(key: typing.Literal[*chars.keys()], val: str) -> bytes:
    return getattr(base64, f'{key}decode')(val.encode())
