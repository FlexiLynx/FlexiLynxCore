#!/bin/python3

'''Sub-parts of the `Blueprint` type'''

#> Imports
import typing
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from FlexiLynx.core.util import base85
#</Imports

#> Header >/
__all__ = ('Manifest', 'Crypt', 'Relations')

_dc = dataclass(slots=True, kw_only=True, weakref_slot=True)

@_dc
class Manifest:
    '''Contains the hashes of files that make up the package'''
    url: str | None
    hash_method: typing.Literal[*hashlib.algorithms_guaranteed] = 'sha1'
    files: dict[Path | str, bytes | str]

    def __post_init__(self):
        self.files = {Path(p): base85.decode(h) if isinstance(h, str) else h
                      for p,h in self.files.items()}

@_dc
class Crypt:
    '''Holds necessary parts for cryptography, namely a key, signature, and the cascade-ring'''
    
    key: EdPubK | bytes | str | None = None
    sig: bytes | str | None = None
    cascade: dict[bytes | str, tuple[EdPubK | bytes | str, EdPubK | bytes | str, bytes | str]] | None

    @staticmethod
    def _to_key(key: EdPubK | bytes | str) -> EdPubK:
        if isinstance(key, str):
            return EdPubK.from_public_bytes(base85.decode(key))
        elif isinstance(self.key, bytes):
            return EdPubK.from_public_bytes(key)
        return key
    def __post_init__(self):
        # key field
        if self.key is not None:
            self.key = self._to_key(self.key)
        # sig field
        if isinstance(self.sig, str):
            self.sig = base85.decode(self.sig)
        # cascade field
        if self.cascade is None: return
        self.cascade = {vkb if isinstance(vkb, bytes) else base85.decode(vkb): (
            self._to_key(vk), self._to_key(tk), (s if isinstance(s, bytes) else base85.decode(s))
        ) for vkb,(vk,tk,s) in self.cascade.items()} # vkb,(vk,tk,s) -> vouching key bytes,(vouching key,target key,signature)

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
