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
from .ManifestExceptions import *

from FlexiLynx.core import packlib
#</Imports

#> Header >/
__all__ = ('Manifest',
           'render_pack', 'load_packed', 'render_json', 'load_json', 'render_ini', 'load_ini',
           'render_to_load', 'load_to_render')

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

    def remap(self, prev_key: EdPrivK, new_key: EdPubK, overwrite: bool = False):
        '''
            Adds a new public key to the remap cascade (or creates a new cascade if one isn't supplied)
                Requires the previous private key to sign the new public key
        '''
        if self.crypt.key_remap_cascade is None:
            self.crypt.key_remap_cascade = {}
        if ((pkpb := prev_key.public_key().public_bytes_raw()) not in self.crypt.key_remap_cascade) or overwrite:
            self.crypt.key_remap_cascade |= {pkpb: (new_key.public_bytes_raw(), prev_key.sign(new_key.public_bytes_raw()))}
        else: raise CascadeOverrideError(self, 'prev_key has already vouched for a key, pass overwrite=True to overwrite')
    CASC_EMPTY = 1
    CASC_INIT_BROKEN = 2
    CASC_BROKEN = 3
    CASC_SIG_REJECTED = 4
    CASC_CIRCULAR = 5
    def chk_cascade(self, target_key: EdPubK, current_key: EdPubK | None = None, *, no_fail: bool = True, debug_callback: typing.Callable[[str, tuple[bytes, ...]], None] = lambda t,v: None) -> None | int:
        '''
            Ensures that the `target_key` is trusted by walking the cascade
            If `current_key` is not given, it is set to this manifest's key
            Example:
                Let `current_key` be key "A" and `target_key` be key "C", with an extra key "B"
                1) Key "A" vouches for key "B". `current_key` is now key "B"
                2) Key "B" vouches for key "C". `current_key` is now key "C"
                3) `current_key` == `target_key`, so the key is trustworthy
            This function returns None upon a success
            Keys can (normally) fail the cascade in the following ways (returning the int if `no_fail`, otherwise raising the exception):
                CASC_EMPTY/EmptyCascadeError, if the cascade is "empty" (evaluates as "falsey", normally an empty dict or None)
                CASC_INIT_BROKEN/InitBrokenCascadeError(BrokenCascadeError), if the *original* `target_key` isn't in the cascade
                CASC_BROKEN/BrokenCascadeError, if the cascade is "broken" (an intermediate/referenced key isn't in the cascade)
                CASC_SIG_REJECTED/CascadeSignatureError from cryptography.exceptions.InvalidSignature, if a signature isn't correct
                CASC_CIRCULAR/CircularCascadeError, if a circular cascade is detected
        '''
        if current_key is None: current_key = self.crypt.public_key
        if __debug__: debug_callback('check', (current_key.public_bytes_raw(), target_key.public_bytes_raw()))
        if not self.crypt.key_remap_cascade:
            if no_fail: return self.CASC_EMPTY
            raise EmptyCascadeError(self, 'cascade is empty')
        if current_key.public_bytes_raw() not in self.crypt.key_remap_cascade:
            if no_fail: return self.CASC_INIT_BROKEN
            raise InitBrokenCascadeError(self, current_key, f'cascade rejected: broken off at initial key {self.crypt._encode_(current_key.public_bytes_raw())}')
        seen = set()
        while (ckb := current_key.public_bytes_raw()) not in seen:
            seen.add(ckb)
            if current_key == target_key:
                if __debug__: debug_callback('match', (ckb, target_key.public_bytes_raw()))
                return None
            if ckb not in self.crypt.key_remap_cascade:
                if no_fail: return self.CASC_BROKEN
                raise BrokenCascadeError(self, current_key, f'cascade rejected: broken off at {self.crypt._encode_(ckb)}')
            nkey,sig = self.crypt.key_remap_cascade[ckb]
            if __debug__: debug_callback('found', (nkey, sig))
            try: current_key.verify(sig, nkey)
            except InvalidSignature:
                if no_fail: return self.CASC_SIG_REJECTED
                raise CascadeSignatureError(self, f'cascade rejected: {self.crypt._encode_(ckb)} does not really vouch for {self.crypt._encode_(nkey)}')
            if __debug__: debug_callback('verify', (ckb, sig, nkey))
            current_key = EdPubK.from_public_bytes(nkey)
        if no_fail: return self.CASC_CIRCULAR
        raise CircularCascadeError(self, f'cascade rejected: circular cascade detected surrounding {self.crypt._encode_(ckb)}')
# Rendering & loading
## packlib
PACK_HEADER = b'\x00\xFFmpack\xFF\x00'
def render_pack(m: Manifest, add_header: bool = True) -> bytes:
    '''Renders a Manifest to bytes via packlib'''
    return (PACK_HEADER if add_header else b'') + m.pack()
def load_packed(p: bytes, take_header: bool = True) -> Manifest:
    '''Loads a Manifest from bytes via packlib'''
    if take_header:
        if not p.startswith(PACK_HEADER):
            raise MissingPackHeaderError('pack rejected - missing header', data=p)
        p = p.removeprefix(PACK_HEADER)
    return Manifest.from_dict(man_packer.unpack(p)[0])
## JSON
JSON_ARRAY_CLEANER_A = re.compile(r'^(\s*"[^"]*":\s*)(\[[^\]]*\])(,?\s*)$', re.MULTILINE)
JSON_ARRAY_CLEANER_B = staticmethod(lambda m: m.group(1)+(re.sub(r'\s+', '', m.group(2)).replace(',', ', '))+m.group(3))
def render_json(m: Manifest, *, compact: bool = False) -> bytes:
    '''Renders a Manifest to JSON'''
    return JSON_ARRAY_CLEANER_A.sub(JSON_ARRAY_CLEANER_B,
                                    json.dumps(m.as_dict(), sort_keys=False) if compact else json.dumps(m.as_dict(), sort_keys=False, indent=4)).encode()
def load_json(j: bytes) -> Manifest:
    '''Loads a Manifest from JSON'''
    return Manifest.from_dict(json.loads(j.decode()))
## INI
def render_ini(m: Manifest) -> bytes:
    '''Renders a Manifest to INI format via configparser'''
    p = ConfigParser(interpolation=None, delimiters=(' = ',)); p.optionxform = lambda o: o
    for ok,ov in m.as_dict().items():
        if ov is None: continue
        p[ok] = {}
        for ik,iv in ov.items():
            if isinstance(iv, dict):
                p[f'{ok}.{ik}'] = {iik: repr(iiv) for iik,iiv in iv.items()}
                continue
            p[ok][ik] = repr(iv)
    with io.StringIO() as stream:
        p.write(stream, space_around_delimiters=False)
        return stream.getvalue().encode()
def load_ini(i: bytes) -> Manifest:
    '''Loads a Manifest from INI format via configparser'''
    p = ConfigParser(interpolation=None, delimiters=(' = ',)); p.optionxform = lambda o: o
    p.read_string(i.decode())
    return Manifest.from_dict(
        {k: # outer items
         {ik: literal_eval(iv) for ik,iv in v.items()} # generic inner items (k[ik] items)
         | {sk.split('.', 1)[1]: # nested inner items (k.sk keys)
            {sik: literal_eval(siv) for sik,siv in p[sk].items()} # nested inner items (k.sk[sik] items)
            for sk in filter(lambda sk: sk.startswith(f'{k}.'), p.keys())} # nested inner items look & predicate
         for k,v in p.items() if (k != 'DEFAULT') and ('.' not in k)}) # outer items loop & predicate
## Pairs
render_to_load = {render_ini: load_ini,
                  render_json: load_json,
                  render_pack: load_packed}
load_to_render = {k: v for v,k in render_to_load.items()}
