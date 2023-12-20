#!/bin/python3

#> Imports
import typing
import hashlib
import base64
from pathlib import Path
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK
## Rendering & Loading
import io
import re
import json
from ast import literal_eval
from configparser import ConfigParser

from .ManifestTypes import *

from FlexiLynx.core import packlib
#</Imports

#> Header >/
__all__ = ('Manifest', 'render_pack',
           'load_packed', 'render_json', 'load_json', 'render_ini', 'load_ini',
           'chk_key_remap_cascade', 'add_key_remap_cascade')

man_packer = packlib.Packer(try_reduce_objects=True)

@dataclass(slots=True, kw_only=True)
class Manifest:
    '''
        Holds data that can bootstrap, install, or update a program
            along with signing and verification methods
    '''

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
    @classmethod
    def from_dict(cls, d: ManifestDict) -> typing.Self:
        return cls(**(d['!'] | {a: None if d.get(a, None) is None else globals()[f'Manifest_{a}']._from_dict_(d[a])
                                for a in ('upstream', 'crypt', 'version', 'metadata', 'relatedepends', 'contentinfo')}
                      | {'contentdata': {f: Manifest_crypt._decode_(d['crypt']['byte_encoding'], s) for f,s in d['contentdata'].items()}}))
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
# Rendering & loading
## packlib
def render_pack(m: Manifest) -> bytes:
    '''Renders a Manifest to bytes via packlib'''
    return m.pack()
def load_packed(p: bytes) -> Manifest:
    '''Loads a Manifest from bytes via packlib'''
    return Manifest.from_dict(man_packer.unpack(packed))
## JSON
JSON_ARRAY_CLEANER_A = re.compile(r'^(\s*"[^"]*":\s*)(\[[^\]]*\])(,?\s*)$', re.MULTILINE)
JSON_ARRAY_CLEANER_B = staticmethod(lambda m: m.group(1)+(re.sub(r'\s+', '', m.group(2)).replace(',', ', '))+m.group(3))
def render_json(m: Manifest, *, compact: bool = False) -> bytes:
    '''Renders a Manifest to JSON'''
    return self.JSON_ARRAY_CLEANER_A.sub(self.JSON_ARRAY_CLEANER_B,
                                         json.dumps(m.as_dict(), sort_keys=False) if compact else json.dumps(m.as_dict(), sort_keys=False, indent=4))
def load_json(j: bytes) -> Manifest:
    '''Loads a Manifest from JSON'''
    return Manifest.from_dict(json.loads(j.decode()))
## INI
def render_ini(m: Manifest) -> bytes:
    '''Renders a Manifest to INI format via configparser'''
    p = ConfigParser(interpolation=None); p.optionxform = lambda o: o
    for ok,ov in m.as_dict().items():
        if ov is None: continue
        p[ok] = {ik: repr(iv) for ik,iv in ov.items()}
    with io.StringIO() as stream:
        p.write(stream)
        return stream.getvalue().encode()
def load_ini(i: bytes) -> Manifest:
    '''Loads a Manifest from INI format via configparser'''
    p = ConfigParser(interpolation=None); p.optionxform = lambda o: o
    with io.StringIO(i.decode()) as stream:
        p.read_string(stream.getvalue())
    return Manifest.from_dict({k: {ik: literal_eval(iv) for ik,iv in v.items()} for k,v in p.items() if k != 'DEFAULT'})
# Key remap cascades
def chk_key_remap_cascade(current_key: EdPubK, target_key: EdPubK, cascade: dict[bytes, tuple[bytes, bytes]]):
    '''
        Ensures that the target_key has not been tampered with by walking the cascade with the current_key
            throws a LookupError if a key wasn't found in the cascade
            throws a cryptography.exceptions.InvalidSignature exception if an entry failed verification
            throws a RecursionError if a circular cascade was detected
    '''
    seen = set()
    while (ckb := current_key.public_bytes_raw()) not in seen:
        seen.add(ckb)
        if current_key == target_key: return
        if ckb not in cascade:
            raise LookupError('cascade rejected - a key was not found in the cascade')
        newkey, newsig = cascade[ckb]
        newkey = EdPubK.from_public_bytes(newkey)
        current_key.verify(newsig, newkey.public_bytes_raw())
        current_key = newkey
    raise RecursionError('cascade rejected - a key was seen twice (assuming to be circular)')
def add_key_remap_cascade(new_key: EdPubK, prev_key: EdPrivK, cascade: dict[bytes, tuple[bytes, bytes]] = {}) -> dict[bytes, tuple[bytes, bytes]]:
    '''
        Adds a new public key to the remap cascade (or creates a new cascade if one isn't supplied)
            Requires the previous private key to sign the new public key
    '''
    return cascade | {prev_key.public_key().public_bytes_raw(): (new_key.public_bytes_raw(), prev_key.sign(new_key.public_bytes_raw()))}
