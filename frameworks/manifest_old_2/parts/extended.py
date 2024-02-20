#!/bin/python3

#> Imports
import typing
from functools import partial
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from . import base

from FlexiLynx.core.util.base85 import decode, encode
#</Imports

#> Header >/
# Setup __all__
__all__ = []
_make_part = partial(base.make_struct_part, add_to_all=__all__)

# Parts classes
@_make_part('cascade')
class KeyCascadePart:
    ring: typing.Mapping[str | bytes | EdPubK, tuple[str | bytes | EdPubK, str | bytes]] | None = None
    def __post_init__(self):
        if self.ring is None:
            self.ring = {}
            return # unnecessary but may save a tiny bit of time in the loop below
        self.ring = {(k := self.transform_key(ok)).public_bytes_raw():
                     (k, self.transform_key(nk), s if isinstance(s, bytes) else decode(s))
                     for ok,(nk,s) in self.ring.items()}
    def __repr__(self) -> str:
        return f'{type(self).__name__}({", ".join(f"""{encode(k)} -> {encode(c[1].public_bytes_raw())}""" for k,c in self.ring.items())})'

    def p_export(self) -> dict[str, [bool | int | float | complex | bytes | str | tuple | frozenset | dict | None]]:
        '''Exports this `KeyCascadePart`'''
        return dict(self._p_export_dict(
            {'ring': {ok: (nk.public_bytes_raw(), s) for ok,(_,nk,s) in self.ring.items()}}))

    @staticmethod
    def _transform_key(kkey: str | bytes | EdPrivK | EdPubK) -> EdPubK:
        '''Transforms `key` into an `EdPubK`'''
        if isinstance(key, EdPubK): return key
        if isinstance(key, EdPrivK): return key.public_key()
        if isinstance(key, str): key = decode(key)
        if isinstance(key, bytes): return EdPubK.from_public_bytes(key)
        raise TypeError(f'Cannot transform {key!r}')

# Finalize __all__
__all__ = tuple(__all__)