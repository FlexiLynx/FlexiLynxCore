#!/bin/python3

#> Imports
import typing
from enum import IntEnum
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from ..parts import extended
from ..base import ManifestType

from FlexiLynx.core.encodings import encode
#</Imports

#> Header >/
__all__ = ('create', 'add_cascade', 'add_key',
           'run_cascade', 'run',
           'CascadeException', 'NotACascadeHolderError', 'UninitializedCascadeError',
           'KeyAlreadyInCascadeError',
           'BrokenCascadeError', 'InvalidCascadeError', 'CircularCascadeError')

# Cascade exceptions
class CascadeException(Exception):
    '''Base exception for cascading issues'''
class NotACascadeHolderError(CascadeException, TypeError):
    '''A cascade method was attempted on a manifest that does not have a `cascade` part'''
class UninitializedCascadeError(CascadeException, ValueError):
    '''A manifest is a cascade holder, but is holding an uninitialized cascade (`None`)'''
## Creation-related exceptions
class KeyAlreadyInCascadeError(CascadeException):
    '''An attempt was made to add a cascade to a ring when the vouching key is already in the ring'''
## Execution-related exceptions
class BrokenCascadeError(CascadeException):
    '''A key wasn't found in the cascade'''
class InvalidCascadeError(CascadeException, InvalidSignature):
    '''A signature in the cascade was invalid'''
class CircularCascadeError(CascadeException):
    '''A key was seen twice whilst walking a cascade'''

# Cascade functions
## Creation
def create(auth: EdPrivK, key: EdPubK) -> tuple[EdPubK, EdPubK, bytes]:
    '''Creates a new cascade, where `auth` "vouches for" (signs) `key`'''
    pauth = auth.public_key()
    return (pauth, key, auth.sign(pauth.public_bytes_raw()+key.public_bytes_raw()))
## Adding
def add_cascade(m: ManifestType, casc: tuple[EdPubK, EdPubK, bytes], *,
                init_empty_cascade: bool = True, overwrite_cascade: bool = False):
    '''Adds a cascade to the manifest'''
    ck = casc[0].public_bytes_raw()
    if not hasattr(m, 'cascade'):
        raise NotACascadeHolderError('Manifest is not a cascade-holder')
    if m.cascade is None:
        if not init_empty_cascade:
            raise UninitializedCascadeError('Manifest is holding an uninitialized cascade (init_empty_cascade=False)')
        m.cascade = extended.KeyCascadePart()
    if (not overwrite_cascade) and (ck in m.cascade.ring):
        raise KeyAlreadyInCascadeError(f'The authorizing key has already trusted another ({ck!r})')
    m.cascade.ring[ck] = casc
def add_key(m: ManifestType, auth: EdPrivK, key: EdPubK, *,
            init_empty_cascade: bool = True, overwrite_cascade: bool = False):
    '''
        Creates a cascade and adds it to the ring, where `auth` "vouches for" (signs) `key`

        Convenience function for `add_cascade(m, create(auth, key), ...)`
    '''
    add_cascade(m, create(auth, key), init_empty_cascade=init_empty_cascade, overwrite_cascade=overwrite_cascade)
## Executing
CascadeResult = IntEnum('CascadeResult', ('UNKNOWN_FAILURE',
                                          'NOT_A_CASCADE_HOLDER', 'UNINITIALIZED_CASCADE',
                                          'BROKEN_CASCADE', 'INVALID_CASCADE', 'CIRCULAR_CASCADE'), start=1)
def run_cascade(ring: typing.Mapping[bytes, tuple[EdPubK, EdPubK, bytes]], target: EdPubK, source: EdPubK, *,
                fail_return: bool = False, info_callback: None | typing.Callable[[typing.Literal['saw', 'check', 'accept'], tuple[bytes, ...]], None] = None) -> None | CascadeResult:
    '''Checks `target` against the `source` key in `casc`'''
    c = source
    seen = set()
    while (cb := c.public_bytes_raw()) not in seen:
        # See the key
        seen.add(cb)
        if info_callback is not None: info_callback('saw', (cb,))
        # Get it from the ring
        if cb not in ring:
            if fail_return: return CascadeResult.BROKEN_CASCADE
            raise BrokenCascadeError(f'The cascade was broken off at key: {encode("b85", cb)!r}')
        rc,rn,rs = ring[cb]
        # Check if something went wrong
        if rc.public_bytes_raw() != cb:
            if fail_return: return CascadeResult.UNKNOWN_FAILURE
            e = CascadeException('A should-be-impossible mismatch was detected; maybe the ring was not created properly?')
            e.add_note(f'(key) {encode("b85", cb)!r} != (val[0]) {encode("b85", rc.public_bytes_raw())!r}')
            raise e
        # Check the cascade
        if info_callback is not None: info_callback('check', (cb, rn.public_bytes_raw(), rs))
        try: rc.verify(rs, cb+rn.public_bytes_raw())
        except InvalidSignature:
            if fail_return: return CascadeResult.INVALID_CASCADE
            raise InvalidCascadeError(f'A key failed verification: {encode("b85", rn.public_bytes_raw())}')
        # Accept the key
        if info_callback is not None: info_callback('accept', (rn.public_bytes_raw(),))
        c = rn
        if c == target: return None # success
    if fail_return: return CascadeResult.CIRCULAR_CASCADE
    raise CircularCascadeError(f'A key was seen twice whilst walking the cascade: {encode("b85", cb)!r}')
def run(m: ManifestType, target: EdPubK, source: EdPubK | None = None, *,
        fail_return: bool = False, info_callback: None | typing.Callable[[typing.Literal['saw', 'check', 'accept'], tuple[bytes, ...]], None] = None) -> None | CascadeResult:
    '''
        Checks `target` against the `source` key in `m`'s cascade
        If `source` is not supplied, the manifest's current key is used

        If `fail_return` is true, then returns a `CascadeResult` instead of raising exceptions
            Successes always return `None` regardless of `fail_return`
    '''
    if source is None: source = m.m_key
    if not hasattr(m, 'cascade'):
        if fail_return: return CascadeResult.NOT_A_CASCADE_HOLDER
        raise NotACascadeHolderError('Manifest is not a cascade-holder')
    if m.cascade is None:
        if fail_return: return CascadeResult.UNINITIALIZED_CASCADE
        raise UninitializedCascadeError('Manifest is holding an uninitialized cascade')
    return run_cascade(m.cascade.ring, target, source, fail_return=fail_return, info_callback=info_callback)
