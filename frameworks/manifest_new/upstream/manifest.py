#!/bin/python3

#> Imports
import typing

from ..file import extract
from ..crypt import migrate
from ..base import Manifest, ManifestType
from ..exceptions import *

from FlexiLynx.core.util import net
#</Imports

#> Header >/
__all__ = ('fetch_manifest', 'update_manifest')

def fetch_manifest(url: str, type_: None | ManifestType = None, *, fetch: typing.Callable[[str], tuple[bytes] | bytes] = net.fetchx) -> Manifest:
    '''Fetches a manifest from `url`, ensures that it is an instance of `type_` if supplied'''
    b = net.fetchx(url)
    if isinstance(b, tuple): b = b[0]
    if (m := extract(b)) is not None:
        if (type_ is None) or (type_.type == m.type): return m
        raise ManifestTypeError(f'{url} is of an unexpected type (expected {type_.type}, got {m.type})')
    raise CorruptedFileException(f'File fetched from {url!r} is not a manifest')
def update_manifest(m: Manifest, migrate_test: bool = True) -> Manifest:
    '''
        Fetches the manifest from `m`'s upstream (under the `metadata` part) and returns it

        Uses `crypt.migrate()` to test the new manifest against the old if `migrate_test` is true
    '''
    if not hasattr(m, 'metadata'):
        raise MissingPartError('Cannot ascertain manifest\'s upstream when it does not have a "metadata" part')
    if getattr(m.metadata, 'upstream', None) is None:
        raise PartTypeError('Manifest\'s metadata.upstream value is either missing or None')
    new = fetch_manifest(m.metadata.upstream, type(m))
    if migrate_test: migrate(new, m)
    return new
