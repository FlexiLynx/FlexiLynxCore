#!/bin/python3

'''
    The basic `Blueprint` type

    Also supplies the `BlueProtocol` type, which allows type-hinting of
        `Blueprint` subclasses that supply specific fields
'''

#> Imports
import typing
from dataclasses import asdict, dataclass, field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from . import parts

from FlexiLynx.core.util import base85
from FlexiLynx.core.util import typing as ftyping
#</Imports

#> Header >/
__all__ = ('Blueprint', 'BlueProtocol')

@dataclass(slots=True, kw_only=True, weakref_slot=True)
class Blueprint:
    '''
        Contains the information needed for packages

        `id` is the unique identification of this blueprint and its package
        `rel` is the release number

        `name` is the human-readable name of the package,
        `desc` is an optional human-readable description of the same,
        and `version` is an optional human-readable version string

        `manifests` are the sets of sets of files that are part of the package

        `relations` are the dependencies and conflicting packages (by ID) of this package
    '''

    id: str = field(kw_only=False)
    rel: int = field(kw_only=False)

    name: str
    desc: str | None = None
    version: str | None = None

    manifests: dict[str, [parts.Manifest | dict]]

    crypt: parts.Crypt | dict

    relations: parts.Relations | dict | None = None

    def __post_init__(self):
        self.manifests = {k: m if isinstance(m, parts.Manifest) else parts.Manifest(**m) for k,m in self.manifests.items()}
        if not isinstance(self.crypt, parts.Crypt): self.crypt = parts.Crypt(**self.crypt)
        if isinstance(self.relations, dict): self.relations = parts.Relations(**self.relations)

    @classmethod
    def _reducing_dict(cls, d: typing.Sequence[tuple[str, typing.Any]]) -> dict:
        return {k: cls._reducing_dict(v.items()) if isinstance(v, dict)
                else base85.encode(v) if isinstance(v, bytes)
                else base85.encode(v.public_bytes_raw()) if isinstance(v, EdPubK)
                else v for k,v in d}
    def to_dict(self) -> dict:
        return asdict(self, dict_factory=self._reducing_dict)

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
