#!/bin/python3

'''Functions for signing and verifying `Blueprint`s'''

#> Imports
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
#</Imports

#> Header >/
__all__ = ('sign', 'verify', 'cascade')

# Simple signing and verifying
def sign(bp: 'blueprint.Blueprint', key: EdPrivK, *, test: bool = True):
    '''Signs the `Blueprint` with `key`, optionally testing it with `verify()`'''
    bp.crypt.key = key.public_key()
    bp.crypt.sig = key.sign(bp.compile())
    if test: verify(bp)
def verify(bp: 'blueprint.Blueprint', key: EdPubK | None = None, *, no_exc: bool = False) -> bool | None:
    '''
        Verifies that a `Blueprint` has not been tampered with
        If `key` is `None`, `bp`'s key is used instead
        If `no_exc` is true, then an `InvalidSignature` will not be raised, instead
            returning `False`
        Note that `no_exc` will not stop `TypeError`s and `ValueError`s
            when `Blueprint` fields are missing
    '''
    if key is None: key = bp.crypt.key
    if key is None:
        raise TypeError('Blueprint is not a keyholder')
    if bp.crypt.sig is None:
        raise ValueError('Blueprint is unsigned')
    if not no_exc:
        key.verify(bp.crypt.sig, bp.compile())
        return None
    try: key.verify(bp.crypt.sig, bp.compile())
    except InvalidSignature: return False
    return True

# Cascading
from . import cascade

# Import `blueprint` to resolve type-hints
from . import blueprint
