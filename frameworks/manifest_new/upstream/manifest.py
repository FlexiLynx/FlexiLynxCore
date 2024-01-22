#!/bin/python3

#> Imports
import typing

from ..file import extract
from ..base import Manifest, ManifestType
from ..exceptions import *

from FlexiLynx.core.ffetch import fancy_fetch
#</Imports

#> Header >/
__all__ = ('fetch_manifest', 'update_manifest')

def fetch_manifest(url: str, type_: None | ManifestType = None, *, fetch: typing.Callable[[str], bytes] = fancy_fetch) -> Manifest:
    '''Fetches a manifest from `url`, ensures that it is an instance of `type_` if supplied'''
    if (m := extract(fetch(url))) is not None:
        if (type_ is None) or (type_.type == m.type): return m
        raise ManifestTypeError(f'{url} is of an unexpected type (expected {type_.type}, got {m.type})')
    raise CorruptedFileException(f'File fetched from {url!r} is not a manifest')
def update_manifest(m: Manifest) -> Manifest:
    '''Fetches the manifest from `m`'s upstream (under the `metadata` part) and returns it'''
    if not hasattr(m, 'metadata'):
        raise MissingPartError('Cannot ascertain manifest\'s upstream when it does not have a "metadata" part')
    if getattr(m.metadata, 'upstream', None) is None:
        raise PartTypeError('Manifest\'s metadata.upstream value is either missing or None')
    return fetch_manifest(m.metadata.upstream, type(m))
