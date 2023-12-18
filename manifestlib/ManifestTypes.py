#!/bin/python3

#> Imports
import time
import dataclasses
import base64, hashlib
import typing, types
from typing import TypedDict, NotRequired
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
#</Imports

#> Header >/
_dataclass = dataclasses.dataclass(slots=True, kw_only=True)
def _manifesttype(cls: type):
    cls.__name__
    if cls.__name__ == '_main_':
        dataname = 'Manifest'
        dictname = ('ManifestDict', 'ManifestDict')
    else:
        dataname = f'Manifest_{cls.__name__}'
        dictname = (f'ManifestDict_{cls.__name__}', f"Manifest['{cls.__name__}']")
    globals()[dataname] = _dataclass(type(dataname, (cls,), dict(cls.__dict__)))
    globals()[dictname[0]] = TypedDict(dictname[1], {a: (NotRequired[typing.get_args(t)[0]]
            if (typing.get_origin(t) in {typing.Union, types.UnionType}) and (typing.get_args(t)[1] in {None, type(None)}) else NotRequired[t])
                if hasattr(cls, a) else t for a,t in cls.__annotations__.items()})
# Upstream
@_manifesttype
class upstream:
    manifest: str
    files: str
    skip_manifest_update: bool | None = None
    skip_content_update: bool | None = None
    def _dict_(self) -> 'ManifestDict_upstream':
        return ManifestDict_upstream(dataclasses.asdict(self))
# Cryptography
ManifestDict_crypt = TypedDict("Manifest['crypt']", {
    'signature': str | None,
    'public_key': str | None,
    'hash_algorithm': NotRequired[typing.Literal[*hashlib.algorithms_available]],
    'byte_encoding': NotRequired[typing.Literal[*set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode')]],
    'key_remap_cascade': NotRequired[dict[str, tuple[str, str]]],
})
@_dataclass
class Manifest_crypt:
    signature: bytes | None
    public_key: EdPubK | None
    hash_algorithm: typing.Literal[*hashlib.algorithms_available] = 'sha1'
    byte_encoding: typing.Literal[*set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode')] = 'b85'
    key_remap_cascade: dict[bytes, tuple[bytes, bytes]] | None = None
    def _encode_(self, b: bytes) -> str:
        return getattr(base64, f'{self.byte_encoding}encode')(b).decode()
    def _dict_(self) -> ManifestDict_crypt:
        return ManifestDict_crypt({
            'signature': None if self.signature is None else self._encode_(self.signature),
            'public_key': None if self.public_key is None else self._encode_(self.public_key.public_bytes_raw()),
            'hash_algorithm': self.hash_algorithm, 'byte_encoding': self.byte_encoding,
            'key_remap_cascade': None if self.key_remap_cascade is None else {self._encode_(k): (self._encode_(v[0]), self._encode_(v[1]))
                                                                                for k,v in self.key_remap_cascade.items()},
        })
# Versioning
@_manifesttype
class version:
    meta_version: str | None = None
    last_update_time: int
    last_update_time_pretty: str
    first_creation_time: int
    first_creation_time_pretty: str
    def _dict_(self) -> 'ManifestDict_version':
        return ManifestDict_version({
            'meta_version': self.meta_version,
            'last_update_time': self.last_update_time,
            'last_update_time_pretty': time.ctime(self.last_update_time),
            'first_creation_time': self.first_creation_time,
            'first_creation_time_pretty': time.ctime(self.first_creation_time),
        })
# Metadata
@_manifesttype
class metadata:
    name: str
    desc: str | None = None
    by: str
    contact: str | None = None
    def _dict_(self) -> 'ManifestDict_metadata':
        return ManifestDict_metadata(dataclasses.asdict(self))
# Relation/depends
@_manifesttype
class relatedepends:
    min_python_version: tuple[int, int, int] | None = None
    python_implementation: str
    platform: str
    before: set[str] | None = None
    after: set[str] | None = None
    requires: set[str] | None = None
    def _dict_(self) -> 'ManifestDict_relatedepends':
        return ManifestDict_relatedepends(dataclasses.asdict(self))
# Contents
@_manifesttype
class contentinfo:
    use_packs: bool | None = None
    skip_files: set[str] | None = None
    def _dict_(self) -> 'ManifestDict_contentinfo':
        return ManifestDict_contentinfo(dataclasses.asdict(self))
Manifest_contentdata = dict[str, bytes]
ManifestDict_contentdata = dict[str, str]
# Final
ManifestDict__ = TypedDict("ManifestDict['!']", {
    'id': str,
    'real_version': int,
    'type': typing.Literal['module', 'plugin', 'other'],
    'format_version': int,
})
ManifestDict = TypedDict('ManifestDict', {
    '!': ManifestDict__,
    'upstream': ManifestDict_upstream | None,
    'crypt': ManifestDict_crypt | None,
    'version': ManifestDict_version,
    'metadata': ManifestDict_metadata,
    'relatedepends': ManifestDict_relatedepends,
    'contentinfo': ManifestDict_contentinfo,
    'contentdata': ManifestDict_contentdata,
})
__all__ = tuple(n for n in dir() if n.startswith('Manifest'))
