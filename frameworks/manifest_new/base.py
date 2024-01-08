#!/bin/python3

#> Imports
import typing

from .parts import *

import FlexiLynx
#</Imports

#> Header >/
__all__ = ('Manifest',)
logger = FlexiLynx.logger.getChild('core.fw.manif')

class _Manifest(base._PartUnion_Hybrid):
    '''
        A base class for all manifests

        Includes `IDManifestPart` and `CryptManifestPart` (from `CoreManifestParts`)
    '''
    __slots__ = ()
class _ManifestMeta(base._PartUnion_HybridMeta):
    def __call__(cls, m_name: str, *, p_defaults: typing.Mapping[str, base.BasePart] = {}, **parts: base.BasePart) -> type[_Manifest]:
        return super().__call__(m_name, *CoreManifestParts.p_struct_cls, _bases=(_Manifest,), **parts)
    def __instancecheck__(cls, other: typing.Any) -> bool:
        return isinstance(other, _Manifest)
    def __subclasscheck__(cls, other: type) -> bool:
        return issubclass(other, _Manifest) or issubclass(other, Manifest)
class Manifest(metaclass=_ManifestMeta):
    __slots__ = ()
    __doc__ = _Manifest.__doc__
