#!/bin/python3

#> Imports
import typing
from pathlib import Path
from collections import abc as cabc
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from . import parts

import FlexiLynx
from FlexiLynx.core import packlib
from FlexiLynx.core.util import concat_mappings, filter_keys
from FlexiLynx.core.encodings import decode, encode
#</Imports

#> Header >/
__all__ = ('ManifestType',)
logger = FlexiLynx.logger.getChild('core.fw.manif')

class _ManifestType:
    '''
        A base class for all manifests

        Includes `IDManifestPart` and `CryptManifestPart`
    '''
    __slots__ = ()
    m_types = {}
    _M_STR_KEY_ENCODING = 'b85'

    def __post_init__(self):
        for n,p in self.m_parts.items():
            if not hasattr(self, n):
                setattr(self, n, None)
                continue
            if isinstance((sp := getattr(self, n)), cabc.Mapping):
                setattr(self, n, p.p_import(sp))
    def __repr__(self) -> str:
        return f'{self.type}(id={self.id!r}, rel={self.rel!r}, ' \
               f'key={"<not a keyholder>" if self.key is None else repr(encode("b85", self.m_key.public_bytes_raw()))}' \
               f'{"".join(f""",\n{" "*len(self.type)} {n}={getattr(self, n)!r}""" for n in self.m_parts.keys())})'

    @property
    def m_key(self) -> EdPubK:
        '''A preprocessed verison of this manifest's key'''
        if (k := getattr(self, 'key', None)) is None:
            raise AttributeError('This manifest is not a keyholder')
        if isinstance(k, bytes): k = EdPubK.from_public_bytes(k)
        if not isinstance(k, EdPubK):
            raise TypeError(f'Cannot resolve manifest key-val {k!r} to a key')
        return k
    @m_key.setter
    def m_key(self, k: EdPubK | EdPrivK | Path | bytes | None):
        '''
            Sets this manifest's key, doing the following transformations:
                `None` -> `None` (unset the key)
                `Path` -> `bytes` (`Path.read_bytes()`)
                `bytes` -> `Ed25519PublicKey` (`Ed25519PublicKey.from_public_bytes()`)
                `Ed25519PrivateKey` -> `Ed25519PublicKey` (`Ed25519PrivateKey.public_key()`)
        '''
        if k is None:
            self.key = None
            return
        if isinstance(k, Path): k = k.read_bytes()
        if isinstance(k, bytes): k = EdPubK.from_public_bytes(k)
        elif isinstance(k, EdPrivK): k = k.public_key()
        if isinstance(k, EdPubK): self.key = k
        else:
            raise TypeError(f'Cannot resolve {k!r} to a key')

    @classmethod
    def m_register(cls):
        '''Registers this manifest class under its `__name__` to allow for later import-discovery'''
        assert cls.type not in cls.m_types, f'{cls.type!r} was already registered by {cls.m_types[cls.type].__qualname__}'
        assert cls not in cls.m_types.values(), f'{cls.type} ({cls.__qualname__}) was already registered under name(s) {", ".join((n for n,c in cls.m_types.items() if c is cls))}'
        cls.m_types[cls.__name__] = cls
    @classmethod
    def m_from_map(cls, m: typing.Mapping) -> typing.Self:
        '''
            Converts a mapping to a manifest, guessing the type with `m["type"]`
            Note that this is different compared to `m_import()` in that it handles any (registered) type of manifest
        '''
        if (c := cls.m_types.get(m['type'], None)) is not None:
            return c.m_import(m)
        raise TypeError(f'Unknown manifest type {m["type"]!r}')

    @classmethod
    def m_import(cls, m: typing.Mapping) -> typing.Self:
        '''
            Converts an exported manifest into an instance of this manifest-class
                Raises `TypeError` if `m['type'] != cls.type`
            Note that this is different compared to `m_from_map()` in that it only works on its own type of manifest
        '''
        if m['type'] != cls.type:
            raise TypeError(f'Type mismatch: this class expects {cls.type}, but the manifest-to-import reports itself as a {m["type"]}')
        return cls(key=None if m['key'] is None else EdPubK.from_public_bytes(m['key']), **filter_keys(lambda k: k not in {'type', 'key'}, m))
    
    def m_export(self) -> dict[str, [bool | int | float | complex | bytes | str | tuple | frozenset | dict | None]]:
        '''
            Converts this manifest into a dictionary of primitive and immutable types
                Uses the underlying parts' `p_export()`
        '''
        return concat_mappings(
            dict(parts.IDManifestPart._p_export_dict({'id': self.id, 'type': self.type, 'rel': self.rel})),
            dict(parts.CryptManifestPart._p_export_dict({'sig': self.sig, 'key': self.key})),
            {n: (v.p_export() if ((v := getattr(self, n, None)) is not None) else None) for n in self.m_parts.keys()},
        )

    def m_compile(self) -> bytes:
        '''
            Compile this manifest for signing
                Note: does *not* compile the `sig` field
        '''
        return packlib.pack(self.m_export() | {'sig': '<stripped>'})
class _ManifestTypeMeta(type):
    def __call__(cls, m_name: str, *, p_defaults: typing.Mapping[str, type[parts.base.BasePart]] = {}, m_register: bool = True, m_top_mutable: bool = True, **p_parts: type[parts.base.BasePart]) -> type[_ManifestType]:
        c = (parts.base._PartUnion_HybridMeta if p_parts else parts.base._PartUnion_NewMeta).__call__(cls,
            m_name, *parts.CoreManifestParts.p_struct_cls, _bases=(_ManifestType,), _namespace={'m_parts': p_parts}, p_mutable=m_top_mutable, **p_parts)
        c.__repr__ = _ManifestType.__repr__
        c.type = m_name
        if m_register: c.m_register()
        return c
    def __instancecheck__(cls, other: typing.Any) -> bool:
        return isinstance(other, _ManifestType)
    def __subclasscheck__(cls, other: type) -> bool:
        return issubclass(other, _ManifestType)
class ManifestType(metaclass=_ManifestTypeMeta):
    __slots__ = ()
    __doc__ = _ManifestType.__doc__

    m_types = _ManifestType.m_types
    m_from_map = _ManifestType.m_from_map
