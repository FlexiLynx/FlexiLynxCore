#!/bin/python3

'''Sub-parts of the `Blueprint` type'''

#> Imports
import typing
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from . import cascade

from . import DEFAULT_HASH_ALGORITHM

from FlexiLynx.core.util import base85
from FlexiLynx.core.util import maptools
#</Imports

#> Header >/
__all__ = ('Manifest', 'Crypt', 'Relations')

_dc = dataclass(slots=True, kw_only=True, weakref_slot=True)

@_dc
class Manifest:
    '''Contains the hashes of files that make up the package'''
    url: str | None
    hash_method: typing.Literal[*hashlib.algorithms_guaranteed] = DEFAULT_HASH_ALGORITHM
    files: dict[str, bytes | str]

    def __post_init__(self):
        self.files = {f: base85.decode(h) if isinstance(h, str) else h
                      for f,h in self.files.items()}
    def serialize_to_dict(self) -> dict:
        return {
            'url': self.url,
            'hash_method': self.hash_method,
            'files': maptools.map_vals(base85.encode, self.files),
        }

@_dc
class Crypt:
    '''Holds necessary parts for cryptography, namely a key, signature, and the cascade-ring'''
    
    key: EdPubK | bytes | str | None = None
    sig: bytes | str | None = None
    cascade: cascade.Types.Cascade | dict[cascade.Types.VoucherB | str,
                                          cascade.Trust | tuple[cascade.Types.Voucher | bytes | str,
                                                                cascade.Types.Vouchee | bytes | str,
                                                                cascade.Types.Signature | str] | dict] | None

    @staticmethod
    def _to_key(key: EdPubK | bytes | str) -> EdPubK:
        if isinstance(key, str):
            return EdPubK.from_public_bytes(base85.decode(key))
        elif isinstance(self.key, bytes):
            return EdPubK.from_public_bytes(key)
        return key
    @classmethod
    def _to_trust(cls, tr: typing.Sequence | typing.Mapping) -> cascade.Trust:
        if isinstance(tr, typing.Mapping):
            tr = (tr['voucher'], tr['vouchee'], tr['signature'])
        return cascade.Trust(voucher=cls._to_key(tr[0]), vouchee=cls._to_key(tr[1]),
                             signature=(tr[2] if isinstance(tr[2], bytes) else base85.decode(tr[2])))
    def __post_init__(self):
        # key field
        if self.key is not None:
            self.key = self._to_key(self.key)
        # sig field
        if isinstance(self.sig, str):
            self.sig = base85.decode(self.sig)
        # cascade field
        if self.cascade is None: return
        self.cascade = {vkb if isinstance(vkb, bytes) else base85.decode(vkb): self._to_trust(trust)
                        for vkb,trust in self.cascade.items()} # vkb,(vk,tk,s) -> vouching key bytes,(vouching key,target key,signature)
    def serialize_to_dict(self) -> dict:
        return {
            'key': None if self.key is None else base85.encode(self.key.public_bytes_raw()),
            'sig': None if self.sig is None else base85.encode(self.sig),
            'cascade': None if self.cascade is None else {base85.encode(vb): dict(zip(cascade.Trust._fields,
                                                                                      map(base85.encode,
                                                                                          (tr.voucher.public_bytes_raw(), tr.vouchee.public_bytes_raw(), tr.signature))))
                                                          for vb,tr in self.cascade.items()},
        }

@_dc
class Relations:
    '''
        Holds information on the package's dependencies and conflicts

        `depends` is a set of package IDs to require before this package may load
            Note that this does **not** imply that package is loaded, merely that it will be
        `conflicts` is a set of package IDs that will cause this package to fail if they are loaded
    '''

    depends: set[str] | typing.Sequence[str]
    conflicts: set[str] | typing.Sequence[str]

    def __post_init__(self):
        self.depends = set(self.depends)
        self.conflicts = set(self.conflicts)
    def serialize_to_dict(self) -> dict:
        return {
            'depends': tuple(self.depends),
            'conflicts': tuple(self.conflicts),
        }
