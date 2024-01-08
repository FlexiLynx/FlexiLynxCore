#!/bin/python3

'''
    Code relating to manifest files themselves

    Manifest files are often INI (.ini) files, but can also be JSON (.json) and PackLib-packed (.pakd) files

    Note that, while not being in `__all__` due to probable lack of use, the `*_preprocess()` and `*_postprocess()` symbols are considered public
'''

#> Imports
import json
import typing
from pathlib import Path
from ast import literal_eval
from configparser import ConfigParser
from collections import abc as cabc

from .base import ManifestType

from FlexiLynx.core import packlib, encodings
from FlexiLynx.core.util import concat_mappings
#</Imports

#> Header >/
__all__ = ('SIG_INI', 'SIG_JSON', 'SIG_PAKD', 'SIG_PAKD_P', 'extract',
           'ini_render', 'ini_extract',
           'json_render', 'json_extract',
           'pakd_render', 'pakd_extract')

SIG_INI    = b';FLMAN\n'
SIG_JSON   = b'{"FLMAN_SIG": null,\n'
SIG_PAKD   = b'\xFFFLMAN\xFF'
SIG_PAKD_P = b'FLMAN_P\n'

def _reduce(s: typing.Sequence | typing.Mapping, *, bytearray_convert: bool, encode_bytes: None | str, set_convert: bool) -> typing.Iterator:
    '''Converts `s` into primitive Python types`'''
    assert not bytearray_convert and encode_bytes, 'Cannot both convert bytearrays to tuples and encode them at once'
    if isinstance(s, cabc.Mapping):
        yield from zip(_reduce(s.keys(), bytearray_convert=bytearray_convert, encode_bytes=encode_bytes, set_convert=set_convert),
                       _reduce(s.values(), bytearray_convert=bytearray_convert, encode_bytes=encode_bytes, set_convert=set_convert))
        return
    for v in s:
        if encode_bytes and isinstance(v, (bytes, bytearray)):
            yield encodings.encode(encode_bytes, v)
        elif isinstance(v, str): yield v
        elif isinstance(v, cabc.Sequence):
            yield tuple(_reduce(v, bytearray_convert=bytearray_convert, encode_bytes=encode_bytes, set_convert=set_convert))
        elif isinstance(v, cabc.Mapping):
            yield dict(_reduce(v, bytearray_convert=bytearray_convert, encode_bytes=encode_bytes, set_convert=set_convert))
        elif bytearray_convert and isinstance(v, bytearray):
            yield tuple(v)
        elif isinstance(v, frozenset):
            yield (tuple if set_convert else frozenset)(
                _reduce(v, bytearray_convert=bytearray_convert, encode_bytes=encode_bytes, set_convert=set_convert))
        else: yield v

def extract(data: bytes | Path) -> ManifestType | None:
    '''
        Automatically chooses the method to extract `data` from its signature
            Returns `None` on a file without a signature
    '''
    if isinstance(data, Path): data = data.read_bytes()
    if data.startswith(SIG_INI): return ini_extract(data)
    if data.startswith(SIG_JSON): return json_extract(data)
    if data.startswith(SIG_PAKD) or data.startswith(SIG_PAKD_P):
        return pakd_extract(data)
    return None

# INI stream
def _ini_preprocess(d: typing.Mapping, _kl: tuple[str, ...] = ()) -> typing.Iterator[tuple[str, str | dict]]:
    m = {}
    for k,v in d.items():
        assert ('.' not in k) and (':' not in k), f'{k} contains illegal character(s) ("." and/or ":")'
        if isinstance(v, cabc.Mapping):
            yield from _ini_preprocess(v, _kl+(k,))
            continue
        try: literal_eval(repr(v))
        except Exception:
            raise TypeError(f'Could not convert key {(".".join(_kl+(k,)))!r} (val={v!r}) to a literal')
        m[repr(k)] = repr(v)
    if m: yield ('.'.join(_kl), m)
def ini_preprocess(man: ManifestType) -> dict:
    '''Convert `man.m_export()` into a suitable format to be read by `ConfigParser`'''
    mexp = man.m_export()
    procd = {'!': {k: repr(v) for k,v in mexp.items() if not isinstance(v, cabc.Mapping)},
             **concat_mappings(*(dict(_ini_preprocess(v, (k,))) for k,v in mexp.items() if isinstance(v, cabc.Mapping)))}
    return procd
def ini_render(man: ManifestType) -> bytes:
    ...
def ini_postprocess(data: bytes) -> bytes:
    ...
def ini_extract(data: bytes | Path) -> ManifestType:
    ...
# JSON stream
def json_preprocess(man: ManifestType) -> dict:
    '''Convert the manifest into JSON-encodable Python types'''
    return dict(_reduce(man.m_export(), bytearray_convert=False, encode_bytes='b85', set_convert=True))
def json_render(man: ManifestType, compact: typing.Literal[0, 1, 2] = 0) -> bytes:
    '''Render the manifest in JSON format'''
    return SIG_JSON + json.dumps(json_preprocess(man), indent=None if compact > 0 else 4,
                                 separators=(',', ':') if compact > 1 else None).encode()[1:]
def json_postprocess(data: bytes) -> str:
    '''Removes `JSON_SIG` from the data and decodes it to a string'''
    return (b'{' + data[len(SIG_JSON):]).decode()
def json_extract(data: bytes | Path) -> typing.Mapping:
    '''
        Extracts a manifest from JSON
            Returns `None` on a file without a `SIG_JSON`
    '''
    if isinstance(data, Path): data = data.read_bytes()
    if not data.startswith(SIG_JSON): return None
    return ManifestType.m_from_map(json.loads(json_postprocess(data)))
# Pakd stream
def pakd_preprocess(man: ManifestType) -> typing.Any:
    '''Simply returns `man.m_export()`'''
    return man.m_export()
def pakd_render(man: ManifestType, printable: bool = False) -> bytes:
    '''Render the manifest into PacLib-packed bytes'''
    return (SIG_PAKD_P if printable else SIG_PAKD) + packlib.pack(pakd_preprocess(man))
def pakd_postprocess(data: bytes, printable: bool) -> bytes:
    '''Decodes (base85) printable bytes if necessary and strips `SIG_PAKD`/`SIG_PAKD_P`'''
    if printable: data = encodings.decode('b85', data.decode())
    return data[len(SIG_PAKD_P if printable else SIG_PAKD):]
def pakd_extract(data: bytes | Path, printable: bool | None = None) -> ManifestType | None:
    '''
        Extracts a manifest from PackLib-packed bytes
            Returns `None` on a file without a `SIG_PAKD` or `SIG_PAKD_P` (depending on `printable`)
    '''
    if isinstance(data, Path): data = data.read_bytes()
    if data.startswith(SIG_PAKD):
        if printable is True: return None
        printable = False
    elif data.startswith(SIG_PAKD_P):
        if printable is False: return None
        printable = True
    else: return None
    return ManifestType.m_from_map(packlib.unpack(pakd_postprocess(data, printable))[0])
