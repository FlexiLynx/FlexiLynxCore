#!/bin/python3

'''
    This file provides debugging tools for packlib-packed data.
    It is hacky and should only be used for testing!
'''

#> Imports
import io
import sys
import time
import itertools
import functools

from .. import packlib
#</Imports

#> Header >/
eprint = functools.partial(print, file=sys.stderr)

def hex1(i: int) -> str:
    return f'0x{hex(i)[2:].upper()}'
def hex2(b: bytes) -> str:
    return ' '.join(map(''.join, itertools.pairwise(b.hex()))).upper()

RECURSE = {packlib.TypeKey.TUPLE, packlib.TypeKey.SET, packlib.TypeKey.DICT, packlib.TypeKey.NAMEDTUPLE}
def packrender(data: bytes, packer: packlib.Packer = packlib.packer, delay: float = 0.5, *, _depth: int = 0):
    eprint(f'Data:\n{hex2(data)}')
    s = io.BytesIO()
    s.write(data)
    s.seek(0)
    if not _depth:
        eprint(f'Size base: {packer._size_base} ({hex1(packer._size_base)})')
        eprint('Types:')
        for t,p in packer._type_to_pfx.items():
            eprint(f'{hex2(p)} => {t!r}')
    eprint(f'--- BEGIN DISASSEMBLE @ {_depth} ---')
    while s.tell() < len(data):
        eprint(f'Start disassemble: pos {s.tell()}:{hex2(data[s.tell():])}')
        eprint(f'{hex2(data[:s.tell()])}|{hex2(data[s.tell():])}')
        eprint(' '*len(hex2(data[:s.tell()])), end='^\n')
        eprint('Running packer.sunarchive_one()...')
        t,d = packer.sunarchive_one(s)
        eprint(f'packer.sunarchive_one() ended at {s.tell()}, got:')
        eprint(f'{t!r} with data {hex2(d) if d else "<blanked>"}')
        eprint(f'Decoded: {packer.decode(t, d)!r}')
        time.sleep(delay)
        if (t in RECURSE) and (input('Recurse? (Y/n) >').lower() != 'n'):
            packrender(d, packer, _depth=_depth+1)
    eprint(f'--- END DISASSEMBLE @ {_depth} ---')
