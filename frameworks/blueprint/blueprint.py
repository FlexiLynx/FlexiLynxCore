#!/bin/python3

'''
    The basic `Blueprint` type

    Also supplies the `BlueProtocol` type, which allows type-hinting of
        `Blueprint` subclasses that supply specific fields
'''

#> Imports
import json
import typing
from dataclasses import dataclass, field, is_dataclass
from collections import abc as cabc
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK

from . import crypt
from . import parts

from FlexiLynx.core.util import base85
from FlexiLynx.core.util import pack
from FlexiLynx.core.util import maptools
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

        `url` is the URL to fetch blueprint updates from
            (package files are fetched from URLs stored in `Manifest`s)

        `main` is the set of files that is a necessary part of the package
        `drafts` is the set of sets of files that are optional parts of the package (alternative languages, versions, etc.)

        `relations` are the dependencies and conflicting packages (by ID) of this package
    '''

    id: str = field(kw_only=False)
    rel: int = field(kw_only=False)

    name: str
    desc: str | None = None
    version: str | None = None

    url: str | None = None

    main: parts.Manifest | dict
    drafts: dict[str, [parts.Manifest | dict]] | None = None

    crypt: parts.Crypt | dict

    relations: parts.Relations | dict | None = None

    def __post_init__(self):
        if not isinstance(self.main, parts.Manifest): self.main = parts.Manifest(**self.main)
        if self.drafts is None: self.drafts = {}
        else:
            self.drafts = {k: m if isinstance(m, parts.Manifest) else parts.Manifest(**m) for k,m in self.drafts.items()}
        if not isinstance(self.crypt, parts.Crypt): self.crypt = parts.Crypt(**self.crypt)
        if isinstance(self.relations, dict): self.relations = parts.Relations(**self.relations)

    @classmethod
    def _reduce_item(cls, i: typing.Any) -> typing.Any:
        if isinstance(i, EdPubK): i = i.public_bytes_raw()
        if isinstance(i, bytes): return base85.encode(i)
        if isinstance(i, (str, cabc.Mapping)): return i
        if isinstance(i, cabc.Iterable): return tuple(map(cls._reduce_item, i))
        if is_dataclass(i): return cls._dc_to_dict(i)
        return i
    @classmethod
    def _reducing_dict(cls, d: typing.Sequence[tuple[str, typing.Any]]) -> dict:
        return maptools.rmap_vals(cls._reduce_item, dict(d))
    @classmethod
    def _dc_to_dict(cls, dc: typing.Any) -> dict:
        return cls._reducing_dict(tuple((f, getattr(dc, f))
                                        for f in dc.__dataclass_fields__.keys()))
    def serialize_to_dict(self) -> dict:
        return self._dc_to_dict(self)
    def serialize(self, **json_args) -> str:
        return json.dumps(self.serialize_to_dict(), indent=4, **json_args)
    @classmethod
    def deserialize_from_dict(cls, data: typing.Mapping) -> typing.Self:
        return cls(**data)
    @classmethod
    def deserialize(cls, data: str) -> typing.Self:
        return cls.deserialize_from_dict(json.loads(data))
    def compile(self) -> bytes:
        '''Compiles this `Blueprint` for signing / verifying'''
        dct = self.serialize_to_dict()
        dct['crypt']['sig'] = NotImplemented
        return pack.pack(dct)

    def sign(self, key: EdPrivK, *, test: bool = True):
        '''Signs the underlying `Blueprint` with `key`, optionally testing the signature after'''
        crypt.sign(self.blueprint, key, test=test)
    def verify(self, key: EdPubK | None = None, *, no_exc: bool = False) -> bool | None:
        '''
            Verifies the signature of this `Blueprint` using `key`
                If `key` is `None`, then this `Blueprint`'s `.key` is used instead
            Raises an `InvalidSignature` on failure,
                unless `no_exc` is true, in which case `False` is returned
        '''
        return crypt.verify(self, key, no_exc=no_exc)
    def migrate(self, key: 'crypt.cascade.Types.Vouchee', *cascs: 'crypt.cascade.Types.Cascade',
                from_key: typing.ForwardRef('crypt.cascade.Types.Voucher') | None = None):
        '''
            Fails if `key` is not an acceptable new key
            `cascs`, if given, will be concatenated to this `Blueprint`'s cascade (if present)
            Raises `TypeError` if no cascades were found
            See `help(crypt.cascade.execute)` for information on exceptions
        '''
        if from_key is None: from_key = self.crypt.key
        if self.crypt.cascade is not None:
            cascs += (self.crypt.cascade,)
        if not cascs:
            raise TypeError('This blueprint does not have a cascade, and none were provided')
        if len(cascs) == 1:
            crypt.cascade.execute(cascs[0], from_key, key)
        else:
            crypt.cascade.multiexec(crypt.cascade.concat(*cascs),
                                    from_key, key)

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
