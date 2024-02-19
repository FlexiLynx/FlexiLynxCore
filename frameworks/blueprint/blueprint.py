#!/bin/python3

'''
    The basic `Blueprint` type

    Also supplies the `BlueProtocol` type, which allows type-hinting of
        `Blueprint`s that supply specific fields
'''

#> Imports
import typing
from dataclasses import dataclass, field, InitVar

from FlexiLynx.core.util import typing as ftyping
#</Imports

#> Header >/
__all__ = ('Blueprint', 'BlueProtocol')

class Baseprint:
    '''Contains the bare minimum fields for a `Blueprint`'''
    __slots__ = ('id', 'rel', 'type', '__dict__', '__weakref__')

    def __init__(self, id: str, rel: int, type: str, /, **kwvals):
        self.id = id
        self.rel = rel
        self.type = type
        self.__dict__ |= kwvals
    def __repr__(self) -> str:
        return f'Blueprint(id={self.id!r}, rel={self.rel!r}, type={self.type!r}, **{self.__dict__})'

@dataclass(slots=True, kw_only=True)
class Blueprint(Baseprint):
    '''Contains most common fields for `Blueprint`s'''

    Baseprint = Baseprint

    id_: InitVar[str] = field(kw_only=False)
    id: str = field(init=False)
    rel_: InitVar[int] = field(kw_only=False)
    rel: int = field(init=False)
    type_: InitVar[int] = field(kw_only=False)
    type: str = field(init=False)

    def __post_init__(self, id: str, rel: int, type: str, /):
        Baseprint.__init__(self, id, rel, type)

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
        return isinstance(other, Baseprint) and super().__instancecheck__(other)
@typing.runtime_checkable
class BlueProtocol(typing.Protocol, metaclass=BlueProtocolMeta):
    '''
        Allows testing if a `Baseprint` instance has required attributes
        Note that `id`, `rel`, and `type` are required in `Baseprint`'s constructor,
            and therefore may not be necessary to specify here
    '''
