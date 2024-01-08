#!/bin/python3

'''Provides functions for manifest cryptography (signing, verifying, etc.)'''

#> Imports
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from .base import ManifestType
#</Imports

#> Header >/
__all__ = ('sign', 'verify')

def sign(m: ManifestType, key: EdPrivK) -> ManifestType:
    '''Signs the manifest `m` in-place (setting `.key` and `.sig` and returns it'''
    m.key = key.public_key()
    m.sig = key.sign(m.m_compile())
    return m
def verify(m: ManifestType, key: EdPubK | None = None, fail_on_missing: bool = False) -> bool | None:
    '''
        Checks if the manifest's signature is valid
        Checks `m.sig` and `m.compile()` against `key` (if supplied) or `m.key`

        When necessary attributes are missing, raises `AttributeError` if `fail_on_missing`, otherwise returns `None`
    '''
    if key is None:
        key = m.key
        if key is None:
            if not fail_on_missing: return None
            raise AttributeError('Manifest is not a keyholder')
    if m.sig is None:
        if not fail_on_missing: return None
        raise AttributeError('Manifest is not signed')
    try: key.verify(m.sig, m.m_compile())
    except InvalidSignature: return False
    return True
