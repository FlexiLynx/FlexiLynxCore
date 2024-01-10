#!/bin/python3

'''
    Core parts of manifests

    Each part contains data, a name, and various helper methods
    Different types of manifests may use different parts
'''

#> Imports
import typing
from functools import partial
from dataclasses import field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from . import base # re-exposed as base
from .base import *
#</Imports

#> Header >/
# Setup __all__
__all__ = ['base',]
_make_part = partial(make_struct_part, add_to_all=__all__)

# Parts classes
## Core parts
@_make_part('!id')
class IDManifestPart:
    id:   str = field(kw_only=False)
    rel:  int = field(kw_only=False)
    type: typing.ClassVar[str]
@_make_part('!crypt')
class CryptManifestPart:
    sig: bytes | None = None
    key: EdPubK | None = None

    @classmethod
    def _p_export_unknown(cls, v: typing.Any):
        if isinstance(v, EdPubK): return v.public_bytes_raw()
        raise TypeError
    @classmethod
    def _p_import_val(cls, k: str, v: typing.Any) -> typing.Any:
        if isinstance(v, EdPubK): pass
        if k == 'key':
            if isinstance(v, bytes): return EdPubK.from_public_bytes(v)
            raise TypeError('Field "key" must be of type "bytes", not {type(v).__qualname__!r}')
        return super()._p_import_val(k, v)

# Part unions
CoreManifestParts = PartUnion('CoreManifestParts', IDManifestPart, CryptManifestPart)
__all__.append('CoreManifestParts')

# Finalize __all__
__all__ = tuple(__all__)
