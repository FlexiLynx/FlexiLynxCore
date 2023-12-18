#!/bin/python3

#> Imports
import typing
import hashlib
import base64
from pathlib import Path
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from .ManifestTypes import *

from FlexiLynx.core import packlib
#</Imports

#> Header >/
__all__ = ('Manifest',)

man_packer = packlib.Packer(try_reduce_objects=True)

@dataclass(slots=True, kw_only=True)
class Manifest:
    id: str
    real_version: int
    type: typing.Literal['module', 'plugin', 'other']
    format_version: int

    upstream: Manifest_upstream
    crypt: Manifest_crypt
    version: Manifest_version
    metadata: Manifest_metadata
    relatedepends: Manifest_relatedepends
    contentinfo: Manifest_contentinfo | None = None
    contentdata: Manifest_contentdata

    def as_dict(self) -> ManifestDict:
        '''Converts this manifest, and all contained attribute-containers, to dictionaries'''
        recurse = ('upstream', 'crypt', 'version', 'metadata', 'relatedepends', 'contentinfo')
        return ManifestDict({'!': ManifestDict__({a: getattr(self, a) for a in ('id', 'real_version', 'type', 'format_version')})}
                            | {a: None if (v := getattr(self, a)) is None else v._dict_() for a in recurse}
                            | {'contentdata': ManifestDict_contentdata({f: self.crypt._encode_(h) for f,h in self.contentdata.items()})})
    def pack(self, *, exclude_sig: bool = False) -> bytes:
        '''Compiles this Manifest via packlib'''
        if not exclude_sig: return man_packer.pack(self.as_dict())
        return man_packer.pack({k: ({vk: vv for vk,vv in v.items() if vk != 'signature'} if k == 'crypt' else v)
                                for k,v in self.as_dict().items()})
    def sign(self, private_key: EdPrivK):
        '''Signs this Manifest and embeds the public key and signature into it'''
        self.crypt.public_key = private_key.public_key()
        self.crypt.signature = private_key.sign(self.pack(exclude_sig=True))
    def verify(self, public_key: EdPubK | None = None) -> bool:
        '''Verifies this Manifest with the given public key, or the embedded key if a key isn't supplied'''
        if public_key is None:
            if self.crypt.public_key is None:
                raise AttributeError('crypt.public_key field is missing and no public key was supplied')
            public_key = self.crypt.public_key
        if self.crypt.signature is None:
            raise AttributeError('crypt.signature field is missing')
        try: public_key.verify(self.crypt.signature, self.pack(exclude_sig=True))
        except InvalidSignature: return False
        return True
