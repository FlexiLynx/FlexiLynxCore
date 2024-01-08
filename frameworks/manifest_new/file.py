#!/bin/python3

'''
    Code relating to manifest files themselves

    Manifest files are often INI (.ini) files, but can also be JSON (.json) and PackLib-packed (.pakd) files
'''

#> Imports
import json
from pathlib import Path

from .base import ManifestType
#</Imports

#> Header >/
__all__ = ('SIG_INI', 'SIG_JSON', 'SIG_PAKD', 'SIG_PAKD_P', 'extract',
           'ini_preprocess', 'ini_render', 'ini_postprocess', 'ini_extract',
           'json_preprocess', 'json_render', 'json_postprocess', 'json_extract',
           'pakd_preprocess', 'pakd_render', 'pakd_postprocess', 'pakd_extract')

SIG_INI    = b';FLMAN\n'
SIG_JSON   = b'{"FLMAN_SIG": null,\n'
SIG_PAKD   = b'\xFFFLMAN\xFF'
SIG_PAKD_P = b'FLMAN_P\n'

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
def ini_preprocess(man: ManifestType) -> typing.Any:
    ...
def ini_render(man: ManifestType) -> bytes:
    ...
def ini_postprocess(data: bytes) -> bytes:
    ...
def ini_extract(data: bytes | Path) -> ManifestType:
    ...
# JSON stream
def json_preprocess(man: ManifestType) -> typing.Any:
    ...
def json_render(man: ManifestType) -> bytes:
    ...
def json_postprocess(data: bytes) -> bytes:
    ...
def json_extract(data: bytes) -> ManifestType:
    ...
# Pakd stream
def pakd_preprocess(man: ManifestType, printable: bool = False) -> typing.Any:
    ...
def pakd_render(man: ManifestType, printable: bool = False) -> bytes:
    ...
def pakd_postprocess(data: bytes) -> bytes:
    ...
def pakd_extract(data: bytes) -> ManifestType:
    ...
