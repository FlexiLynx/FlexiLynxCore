#!/bin/python3

#> Imports
import typing

from .parts import *

import FlexiLynx
#</Imports

#> Header >/
__all__ = ('ManifestType',)
logger = FlexiLynx.logger.getChild('core.fw.manif')

class _ManifestType(base._PartUnion_Hybrid):
    '''
        A base class for all manifests

        Includes `IDManifestPart` and `CryptManifestPart` (from `CoreManifestParts`)
    '''
    __slots__ = ()
    m_types = {}

    def m_register(self, name: str):
        assert name not in self.m_types, f'{name!r} was already registered by {self.m_types[name].__qualname__}'
        assert cls not in self.m_types.values(), f'{self.__qualname__} was already registered under name(s) {", ".join((n for n,c in self.m_types.items() if c is self))}'
        self.m_types[name] = self
class _ManifestTypeMeta(base._PartUnion_HybridMeta):
    def __call__(cls, m_name: str, *, p_defaults: typing.Mapping[str, base.BasePart] = {}, **parts: base.BasePart) -> type[_ManifestType]:
        return super().__call__(m_name, *CoreManifestParts.p_struct_cls, _bases=(_ManifestType,), **parts)
    def __instancecheck__(cls, other: typing.Any) -> bool:
        return isinstance(other, _ManifestType)
    def __subclasscheck__(cls, other: type) -> bool:
        return issubclass(other, _ManifestType) or issubclass(other, ManifestType)
class ManifestType(metaclass=_ManifestTypeMeta):
    __slots__ = ()
    __doc__ = _ManifestType.__doc__

    m_types = _ManifestType.m_types
    m_register = _ManifestType.m_register
