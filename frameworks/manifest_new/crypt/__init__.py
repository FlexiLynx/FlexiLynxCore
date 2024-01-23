#!/bin/python3

'''Provides functions for manifest cryptography (signing, verifying, etc.)'''

#> Imports
import typing
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from .. import base
from .. import exceptions
from ..base import logger
from . import cascade # re-exposed

from FlexiLynx.core.encodings import encode
#</Imports

#> Header >/
__all__ = ('cascade', 'sign', 'verify', 'migrate')

def sign(m: base.Manifest, key: EdPrivK) -> base.Manifest:
    '''Signs the manifest `m` in-place (setting `.key` and `.sig` and returns it'''
    m.m_key = key
    m.sig = key.sign(m.m_compile())
    return m
def verify(m: base.Manifest, key: EdPubK | None = None, fail_on_missing: bool = False) -> bool | None:
    '''
        Checks if the manifest's signature is valid
        Checks `m.sig` and `m.compile()` against `key` (if supplied) or `m.key`

        When necessary attributes are missing, raises `AttributeError` if `fail_on_missing`, otherwise returns `None`
    '''
    if key is None:
        try:
            key = m.m_key
        except AttributeError:
            if fail_on_missing: raise
            return None
    if m.sig is None:
        if not fail_on_missing: return None
        raise AttributeError('Manifest is not signed')
    try: key.verify(m.sig, m.m_compile())
    except InvalidSignature: return False
    return True

def _migrate_cascaderun_icallb(loc: typing.Literal['saw', 'check', 'accept'], args: tuple[bytes, ...]):
    match loc:
        case 'saw':
            logger.debug(f'Cascade: Saw key {encode("b85", args[0])}')
        case 'check':
            logger.verbose(f'Cascade: Checking new key {encode("b85", args[1])}')
            logger.debug(f'Cascade: Checking below signature with key: {encode("b85", args[0])}\n{encode("b85", args[2])}')
        case 'accept':
            logger.info(f'Cascade: Accepted new key {encode("b85", args[0])}')
def _migrate_dualcascaderun_icallb(loc: typing.Literal['saw', 'check', 'accept', 'swap', 'split', 'reject'], state: bool, depth: int, args: tuple[bytes, ...]):
    pfx = f'Cascade{"B" if state else "A"}[{depth}]'
    match loc:
        case 'saw':
            logger.debug(f'{pfx}: Saw key {encode("b85", args[0])}')
        case 'check':
            logger.verbose(f'{pfx}: Checking new key {encode("b85", args[1])}')
            logger.debug(f'{pfx}: Checking:\nsignature {encode("b85", args[2])}\nwith key {encode("b85", args[0])}')
        case 'accept':
            logger.info(f'{pfx}: Accepted new key {encode("b85", args[0])}')
        case 'swap':
            logger.info(f'{pfx}: Swapped cascades')
        case 'split':
            logger.verbose(f'{pfx}: Checking divergent cascades')
        case 'reject':
            logger.info(f'{pfx}: Rejected split')
def migrate(target: base.Manifest, local: base.Manifest, cascade_target: bool = True, cascade_local: bool = True):
    '''
        Checks if `target` is a secure update for `local` with `verify()`
        Additionally checks cascades for target and local respectively if `cascade_target` or `cascade_local` and if the keys differ
            (these have to effect if the respective manifest is not a cascade-holder)
            If both `cascade_target` and `cascade_local` true, then instead uses `cascade.run_many()`
        Returns nothing upon a succes, and upon failure raises the following exceptions:
            `ValueError` if `cascade_target` and `cascade_local` are both false and `target` and `local`'s keys don't match
            `cascade.NotACascadeHolderError` if neither manifests have (initialized) cascades when trying to run both cascades
            Any exceptions raised from `cascade.run()` or `cascade.dualrun()`
            `AttributeError` if `target` or `local` are missing keys, or if `target` is not signed
            A `cryptography.exceptions.InvalidSignature` if `verify()` returns false
    '''
    if target.m_key != local.m_key:
        logger.warning(f'Target key differs from local key:\nlocal:  {encode("b85", local.m_key.public_bytes_raw())}\ntarget: {encode("b85", target.m_key.public_bytes_raw())}')
        if not (cascade_target or cascade_local):
            raise ValueError('Target key differs from local key, and both cascade_target and cascade_local are false')
        cascade_target = cascade_target and (getattr(target, 'cascade', None) is not None)
        cascade_local = cascade_local and (getattr(local, 'cascade', None) is not None)
        if not (cascade_target or cascade_local):
            raise cascade.NotACascadeHolderError('Keys differ and neither manifest holds a(n initialized) cascade')
        if cascade_target and cascade_local:
            logger.warning('Checking key remap against dual cascades')
            cascade.dualrun(target.m_key, local.m_key, local.cascade.ring, target.cascade.ring, info_callback=_migrate_dualcascaderun_icallb)
        else:
            logger.warning(f'Checking key remap against "{"target" if cascade_target else "local"}"\'s cascade')
            cascade.run(target.m_key, local.m_key, target if cascade_target else local, info_callback=_migrate_cascaderun_icallb)
        logger.info(f'Key remap accepted: {encode("b85", target.m_key.public_bytes_raw())}')
    if not verify(target): # we trust target's key as it is either the same as local's or was verified through a cascade, so just verify with that one
        raise InvalidSignature('Target manifest\'s signature was rejected')
