#!/bin/python3

#> Imports
import types
import typing

from .parts import *

import FlexiLynx
from FlexiLynx.core.util import concat_mappings
from FlexiLynx.core.packlib import Packer
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
        if m['type'] != cls['type']:
            raise TypeError(f'Type mismatch: this class expects {cls["type"]}, but the manifest-to-import reports itself as a {m["type"]}')
        return cls(**filter_keys(lambda k: k != 'type'))
    def m_export(self) -> types.MappingProxyType[str, [bool | int | float | complex | bytes | str | tuple | frozenset | types.MappingProxyType | None]]:
        '''
            Converts this manifest into a dictionary (`mappingproxy`) of primitive and immutable types
                Uses the underlying parts' `p_export()`
        '''
        return types.MappingProxyType(concat_mappings(
            IDManifestPart._p_export_dict({'id': self.id, type: self.type, 'rel': self.rel}),
            CryptManifestPart._p_export_dict({'sig': self.sig, 'key': self.key}),
            {n: (v.p_export() if ((v := getattr(self, n, None)) is not None) else None) for n in self.m_parts.keys()},
        ))

    M_packer = Packer(try_reduce_objects=True)
    def m_compile(self) -> bytes:
        '''Compile this manifest for signing'''
        return self.M_packer.pack(self)
class _ManifestTypeMeta(type):
    def __call__(cls, m_name: str, *, p_defaults: typing.Mapping[str, base.BasePart] = {}, m_register: bool = True, **parts: base.BasePart) -> type[_ManifestType]:
        c = (base._PartUnion_HybridMeta if parts else base._PartUnion_NewMeta).__call__(cls,
            m_name, *CoreManifestParts.p_struct_cls, _bases=(_ManifestType,), _namespace={'m_parts': parts}, **parts)
        c.type = m_name
        if m_register: c.m_register()
        return c
    def __instancecheck__(cls, other: typing.Any) -> bool:
        return isinstance(other, _ManifestType)
    def __subclasscheck__(cls, other: type) -> bool:
        return issubclass(other, _ManifestType) or issubclass(other, ManifestType)
class ManifestType(metaclass=_ManifestTypeMeta):
    __slots__ = ()
    __doc__ = _ManifestType.__doc__

    m_types = _ManifestType.m_types
    m_from_map = _ManifestType.m_from_map
