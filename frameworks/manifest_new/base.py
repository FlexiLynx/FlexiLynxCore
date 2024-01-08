#!/bin/python3

#> Imports
import typing

from .parts import *

import FlexiLynx
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
        assert cls.__name__ not in cls.m_types, f'{cls.__name__!r} was already registered by {cls.m_types[cls].__qualname__}'
        assert cls not in cls.m_types.values(), f'{cls.__name__} ({cls.__qualname__}) was already registered under name(s) {", ".join((n for n,c in cls.m_types.items() if c is cls))}'
        cls.m_types[cls.__name__] = cls
    @classmethod
    def m_from_map(cls, m: typing.Mapping) -> typing.Self:
        '''Converts a mapping to a manifest, guessing the type with `m["type"]`'''
        if (c := cls.m_types[m['type']]) is not None:
            return c(**m['type'])
        raise TypeError(f'Unknown manifest type {m["type"]!r}')
class _ManifestTypeMeta(base._PartUnion_HybridMeta):
    def __call__(cls, m_name: str, *, p_defaults: typing.Mapping[str, base.BasePart] = {}, m_register: bool = True, **parts: base.BasePart) -> type[_ManifestType]:
        namespace = {'type': m_name, 'm_parts': parts}
        c = super().__call__(m_name, *CoreManifestParts.p_struct_cls, _bases=(_ManifestType,), _namespace=namespace, **parts) \
            if parts else type(m_name, (CoreManifestParts, _ManifestType,), namespace)
        if m_settype: c.type = m_name
        if m_register:
            assert m_settype, 'Cannot register without setting type'
            c.m_register()
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
