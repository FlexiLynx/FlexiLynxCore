#!/bin/python3

'''
    Provides some utilities for working with Base85 text

    Base85 is used as the bytes-to-text encoding of choice in FlexiLynx
        due to its relatively compact size (compared to 16 or 64) and alright-looking character set
    Methods that start with `b` work with "encoded" (`bytes`) strings instead of Python `str`s
    `chars` and `patt` are automatically generated upon import
'''

#> Imports
import re
import base64
import typing

from .tools.retools import char_patt
#</Imports

#> Header >/
__all__ = ('encode', 'bencode',
           'decode', 'bdecode',
           'chars', 'patt')

def encode(b: bytes) -> str:
    '''Encodes `b` in Base85 as a string'''
    return bencode(b).decode()
def bencode(b: bytes) -> bytes:
    '''Encodes `b` in Base85 as a byte-string'''
    return base64.b85encode(b)
def decode(s: str) -> bytes:
    '''Decodes a Base85-encoded string `s` into bytes'''
    return bdecode(s.encode())
def bdecode(s: bytes) -> bytes:
    '''Decodes a Base85-encoded byte-string `s` into bytes'''
    return base64.b85decode(s)

chars = set(base64.b85encode(bytes(range(0, 255*4//5-1))))
patt = re.compile(char_patt(bytes(chars).decode()))
