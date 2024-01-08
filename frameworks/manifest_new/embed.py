#!/bin/python3

'''
    Provides facilities for embedding manifests into Python files and extracting them

    Note that the following symbols are public, despite not being in `__all__` due to the low possibility of use compared to other symbols:
      - `embed_manifest_dict()`
      - `embed_packed_manifest_dict()`
      - `extract_manifest_dict()`
      - `extract_packed_manifest_dict()`
'''

#> Imports
import re

from FlexiLynx.core import encodings, packlib
#</Imports

#> Header >/
__all__ = ('embed_manifest', 'strip_manifest', 'extract_manifest')

encoding = 'b85'
embed_str = '__EMBEDDED_MANIFEST__ = {}'
embed_patt = re.compile(fr'''^{embed_str.format(f"""'({encodings.char_patts["b85"].pattern}+)'""")}(?:\n|$)''')
def embed_manifest(contents: str, man: 'Manifest') -> str:
    '''Embeds a manifest object into a Python file'''
    raise NotImplementedError
def embed_manifest_dict(contents: str, man: dict) -> str:
    '''Embeds a dictionary into a Python file'''
    return embed_packed_manifest_dict(contents, packlib.pack(man))
def embed_packed_manifest_dict(contents: str, packed: bytes) -> str:
    '''Embeds a packed manifest dict into a Python file'''
    return f'{embed_str.format(repr(encodings.encode(encoding, packed)))}\n{strip_manifest(contents)}'
def strip_manifest(contents: str) -> str:
    '''Strips an embedded manifest rom a Python file'''
    return embed_patt.sub('', contents)
def extract_manifest(contents: str) -> None:
    '''Extracts an embedded manifest from a Python file'''
    raise NotImplementedError
def extract_manifest_dict(contents: str) -> dict | None:
    '''Extracts a manifest dictionary from a Python file'''
    if (p := extract_packed_manifest_dict(contents)) is not None:
        return packlib.unpack(p)[0]
    return None
def extract_packed_manifest_dict(contents: str) -> bytes | None:
    '''Extracts a packed manifest dictionary from a Python file'''
    if m := embed_patt.match(contents):
        return encodings.decode(encoding, m.group(1))
    return None
