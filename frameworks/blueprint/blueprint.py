#!/bin/python3

'''
    The basic `Blueprint` type

    Also supplies the `BlueProtocol` type, which allows type-hinting of
        `Blueprint` subclasses that supply specific fields
'''

#> Imports
import json
import typing
from enum import Enum
from dataclasses import dataclass, field, is_dataclass
from collections import abc as cabc
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK

from . import crypt
from . import parts

from . import logger

from FlexiLynx.core.util import base85
from FlexiLynx.core.util import pack
from FlexiLynx.core.util import maptools
from FlexiLynx.core.util import typing as ftyping
from FlexiLynx.core.util.net import fetch1
from FlexiLynx.core.util.functools import defaults, DEFAULT
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

    @defaults(crypt.sign)
    def sign(self, key: EdPrivK, *, test: bool = DEFAULT):
        '''Signs the underlying `Blueprint` with `key`, optionally testing the signature after'''
        crypt.sign(self, key, test=test)
    @defaults(crypt.verify)
    def verify(self, key: EdPubK | None = None, *, no_exc: bool = DEFAULT) -> bool | None:
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

    KeyUpdate = Enum('KeyUpdate', ('MIGRATE_SELF', 'MIGRATE_OTHER', 'MIGRATE_BOTH', 'FAIL', 'IGNORE'))
    def update(self, url: str | None = None, *, fetchfn: typing.Callable[[str], bytes] = fetch1,
               verify: bool = True, verify_self: bool = False, key_update: KeyUpdate = KeyUpdate.MIGRATE_BOTH) -> typing.Self:
        '''
            Fetches an update for this `Blueprint`, returning the *new* `Blueprint`
            If `url` is not `None`, it overrides this `Blueprint`'s `.url`
            Runs `Blueprint.verify()` on the new `Blueprint` if `verify` is true,
                and `Blueprint.verify()` on the current `Blueprint` if `verify_self` is true
            If the new `Blueprint`'s key is different from the current one, then `key_update` determines the behavior:
              - `KeyUpdate.MIGRATE_SELF`: migrate the key using this `Blueprint`'s cascade
              - `KeyUpdate.MIGRATE_OTHER`: migrate the key using the new `Blueprint`'s cascade
              - `KeyUpdate.MIGRATE_BOTH`: migrate the key using both cascades
              - `KeyUpdate.FAIL`: raise a `RuntimeError`
              - `KeyUpdate.IGNORE`: continue as normal
                Any other value results in a `ValueError`
                In the `.MIGRATE_*` behaviors, `TypeError` is raised if a necessary cascade is missing
        '''
        if url is None: url = self.url
        if url is None:
            raise TypeError('No URL was provided and this blueprint has no URL')
        logger.terse(f'Update issued: {self.id} from {url!r}')
        if verify_self:
            logger.info('Verifying self')
            self.verify()
        other = self.deserialize(fetchfn(url).decode())
        if verify:
            logger.info('Verifying other')
            other.verify()
        if self.crypt.key != other.crypt.key:
            logger.warning(f'Key mismatch, taking action {key_update!r} on:\n'
                           f'Self:  {base85.encode(self.crypt.key)}\n'
                           f'Other: {base85.encode(other.crypt.key)}')
            if key_update is self.KeyUpdate.MIGRATE_BOTH:
                if self.crypt.key is None:
                    if other.crypt.key is None:
                        raise TypeError('Cannot MIGRATE_BOTH; both cascades are missing')
                    key_update = self.KeyUpdate.MIGRATE_OTHER
                elif other.crypt.key is None:
                    key_update = self.KeyUpdate.MIGRATE_SELF
            match key_update:
                case self.KeyUpdate.FAIL: raise RuntimeError('Refusing to accept new key (key_update is KeyUpdate.FAIL)')
                case self.KeyUpdate.MIGRATE_SELF:
                    if self.crypt.cascade is None:
                        raise TypeError('Cannot MIGRATE_SELF; self is missing a cascade')
                    logger.terse('Migrating key using self\'s cascade')
                    self.migrate(other.crypt.key)
                case self.KeyUpdate.MIGRATE_OTHER:
                    if other.crypt.cascade is None:
                        raise TypeError('Cannot MIGRATE_OTHER; other is missing a cascade')
                    logger.terse('Migrating key using other\'s cascade')
                    other.migrate(other.crypt.key, from_key=self.crypt.key)
                case self.KeyUpdate.MIGRATE_BOTH:
                    logger.terse('Migrating key using both self and other\'s cascade')
                    self.migrate(other.crypt.key, other.crypt.cascade)
                    logger.info('Successfully migrated key using both cascades')
                case _: raise ValueError(f'Unacceptable value for key_update: {key_update!r}')
        return other

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
