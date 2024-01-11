#!/bin/python3

#> Imports
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from ..parts import extended
from ..base import ManifestType
#</Imports

#> Header >/
__all__ = ('create', 'add_cascade', 'add_key',
           'CascadeException', 'NotACascadeHolderError', 'UninitializedCascadeError', 'KeyAlreadyInCascadeError')

# Cascade exceptions
class CascadeException(Exception):
    '''Base exception for cascading issues'''
class NotACascadeHolderError(CascadeException, TypeError):
    '''A cascade method was attempted on a manifest that does not have a `cascade` part'''
class UninitializedCascadeError(CascadeException, ValueError):
    '''A manifest is a cascade holder, but is holding an uninitialized cascade (`None`)'''
class KeyAlreadyInCascadeError(CascadeException):
    '''An attempt was made to add a cascade to a ring when the vouching key is already in the ring'''

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
