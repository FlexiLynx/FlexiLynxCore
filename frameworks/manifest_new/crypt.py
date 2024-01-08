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
def verify(m: ManifestType, key: EdPubK | None = None) -> bool:
    '''
        Checks if the manifest's signature is valid
        Checks against `key` if it isn't none, otherwise against `m.key`
    '''
    try: (m.key if key is None else key).verify(m.sig, m.compile())
    except InvalidSignature: return False
    return True
