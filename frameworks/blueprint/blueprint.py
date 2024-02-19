#!/bin/python3

'''
    The basic `Blueprint` type

    Also supplies the `BlueProtocol` type, which allows type-hinting of
        `Blueprint` subclasses that supply specific fields
'''

#> Imports
import typing
from dataclasses import dataclass, field, InitVar

from FlexiLynx.core.util import typing as ftyping
#</Imports

#> Header >/
__all__ = ('Blueprint', 'BlueProtocol')

@dataclass(slots=True, kw_only=True, weakref_slot=True)
class Blueprint:
    '''Contains the information needed for packages'''

    id: str = field(kw_only=False)
    rel: int = field(kw_only=False)


# Protocol
class BlueProtocolMeta(type(typing.Protocol)):
    def __call__(cls, _name: str = '<BlueProtocol>', _doc: str | None = None, _module: str = '<BlueProtocol>', **_annotations):
        return ftyping.Protocol(_name, _doc, _module, (BlueProtocol, typing.Protocol), **_annotations)
        return type(_name, (BlueProtocol, typing.Protocol), {
            '__annotations__': _annotations,
            '__protocol_attrs__': frozenset(_annotations.keys()),
            '__doc__': _doc, '__module__': _module,
        })
    def __instancecheck__(self, other: object) -> bool:
        return isinstance(other, Blueprint) and super().__instancecheck__(other)
@typing.runtime_checkable
class BlueProtocol(typing.Protocol, metaclass=BlueProtocolMeta):
    '''Allows testing if a `Blueprint` instance has required attributes'''
