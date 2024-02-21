#!/bin/python3

'''
    Functions for creating and executing trusts and cascades
    Terminology:
        "voucher": a public key that vouches for another public key ("vouchee") in a trust
        "vouchee": a public key that is vouched for by a "voucher"
        "trust": a "voucher", "vouchee", and signature
        "chain": when multiple trusts link together (each "vouchee" becomes a "voucher" in turn until the end is reached)
        "cascade": a set of "trust"s, which may or may not contain multiple interlinking, or one singular, "chain"
'''

#> Imports
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
#</Imports

#> Header >/
__all__ = (
    'TVoucherPrK', 'TVoucher', 'TVoucherB', 'TVouchee', 'TSignature', 'TTrust', 'TCascade',
    'gen_trust', 'run_trust',
    'add_trust', 'add',
)

# Types
type TVoucherPrK = EdPrivK
type TVoucher = EdPubK
type TVoucherB = bytes
type TVouchee = EdPubK
type TSignature = bytes
type TTrust = tuple[TVoucher, TVouchee, TSignature]
type TCascade = dict[TVoucherB, TTrust]

# Functions
## Trusts
def gen_trust(voucher: TVoucherPrK, vouchee: TVouchee) -> TTrust:
    '''Generates a trust, where `voucher` vouches for `vouchee`'''
    pubk = voucher.public_key()
    return (pubk, vouchee, voucher.sign(pubk.public_bytes_raw() + vouchee.public_bytes_raw()))
def run_trust(trust: TTrust, *, no_exc: bool = False) -> bool | None:
    '''Executes a trust, raising an `InvalidSignature` if it's invalid (or returning `False` if `no_exc`)'''
    ver,vee,sig = trust
    if not no_exc:
        ver.verify(trust[2], trust[0].public_bytes_raw() + trust[1].public_bytes_raw())
        return None
    try: ver.verify(trust[2], trust[0].public_bytes_raw() + trust[1].public_bytes_raw())
    except InvalidSignature: return False
    return True
## Cascades
### Adding
def add_trust(casc: TCascade, trust: TTrust, *, overwrite: bool = False):
    '''
        Adds a `trust` to `casc`
        Raises `KeyError` if the vouching key is already present in the cascade,
            unless `overwrite` is true
    '''
    pb = trust[0].public_bytes_raw()
    if (not overwrite) and (pb in casc):
        raise KeyError('Refusing to overwrite a trust already present in the cascade when overwrite is false')
    casc[pb] = trust
def add(casc: TCascade, voucher: TVoucherPrK, vouchee: TVouchee, *, overwrite: bool = False):
    '''
        Generates a new trust and adds it to `casc`
        Raises `KeyError` if the vouching key is already present in the cascade,
            unless `overwrite` is true
    '''
    add_trust(casc, gen_trust(voucher, vouchee), overwrite=overwrite)
