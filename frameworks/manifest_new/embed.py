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

from .base import ManifestType

from FlexiLynx.core import encodings, packlib
#</Imports

#> Header >/
__all__ = ('embed_manifest', 'strip_manifest', 'extract_manifest')

encoding = 'b85'
embed_str = "__EMBEDDED_MANIFEST__ = ('{type}', '{pack}')"
pack_patt = f'(?P<pack>{encodings.char_patts["b85"].pattern}+)'
type_patt = r'(?P<type>[!#-&(-\[\]-~])'
embed_patt = re.compile(fr'''^{embed_str.format(type=type_patt, pack=pack_patt)}(?:\n|$)''')
def embed_manifest(contents: str, man: ManifestType) -> str:
    '''Embeds a manifest object into a Python file'''
    return embed_manifest_dict(contents, man.p_export(), man.type)
def embed_manifest_dict(contents: str, man: dict, type_key: str) -> str:
    '''Embeds a dictionary into a Python file'''
    return embed_packed_manifest_dict(contents, packlib.pack(man), type_key)
def embed_packed_manifest_dict(contents: str, packed: bytes, type_key: str) -> str:
    '''Embeds a packed manifest dict into a Python file'''
    return f'{embed_str.format(type=type_key, pack=encodings.encode(encoding, packed))}\n{strip_manifest(contents)}'
def strip_manifest(contents: str) -> str:
    '''Strips an embedded manifest rom a Python file'''
    return embed_patt.sub('', contents)
def extract_manifest(contents: str) -> ManifestType | None:
    '''Extracts an embedded manifest from a Python file'''
    return ManifestType.m_from_map(d) if (d := extract_manifest_dict(contents)) is not None else None
def extract_manifest_dict(contents: str) -> tuple[str, dict] | None:
    '''Extracts a manifest type-key and manifest dictionary from a Python file'''
    if (p := extract_packed_manifest_dict(contents)) is not None:
        return packlib.unpack(p)[0]
    return None
def extract_packed_manifest_dict(contents: str) -> tuple[str, bytes] | None:
    '''Extracts a manifest type-key and packed manifest dictionary and from a Python file'''
    if m := embed_patt.match(contents):
        return encodings.decode(encoding, m.group(1))
    return None
