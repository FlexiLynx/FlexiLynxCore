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
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
#</Imports

#> Header >/
__all__ = (
    'TVoucherPrK', 'TVoucher', 'TVoucherB', 'TVouchee', 'TSignature', 'TTrust', 'TCascade',
)

# Types
type TVoucherPrK = EdPrivK
type TVoucher = EdPubK
type TVoucherB = bytes
type TVouchee = EdPubK
type TSignature = bytes
type TTrust = tuple[TVoucher, TVouchee, TSignature]
type TCascade = dict[TVoucherB, TTrust]
