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
import typing
from types import SimpleNamespace
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
#</Imports

#> Header >/
__all__ = ('Types',
           'gen_trust', 'run_trust',
           'add_trust', 'add', 'pop', 'walk', 'execute')

# Types
_TVoucher = typing.TypeAliasType('Voucher', EdPubK)
_TVoucherB = typing.TypeAliasType('VoucherB', bytes)
_TVouchee = typing.TypeAliasType('Vouchee', EdPubK)
_TSignature = typing.TypeAliasType('Signature', bytes)
_TTrust = typing.TypeAliasType('Trust', tuple[_TVoucher, _TVouchee, _TSignature])
Types = SimpleNamespace(
    VoucherPrK = typing.TypeAliasType('VoucherPrK', EdPrivK),
    Voucher = _TVoucher,
    VoucherB = _TVoucherB,
    Vouchee = _TVouchee,
    Signature = _TSignature,
    Trust = _TTrust,
    Cascade = typing.TypeAliasType('Cascade', dict[_TVoucherB, _TTrust]),
)

# Functions
## Trusts
def gen_trust(voucher: Types.VoucherPrK, vouchee: Types.Vouchee) -> Types.Trust:
    '''Generates a trust, where `voucher` vouches for `vouchee`'''
    pubk = voucher.public_key()
    return (pubk, vouchee, voucher.sign(pubk.public_bytes_raw() + vouchee.public_bytes_raw()))
def run_trust(trust: Types.Trust, *, no_exc: bool = False) -> bool | None:
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
def add_trust(casc: Types.Cascade, trust: Types.Trust, *, overwrite: bool = False):
    '''
        Adds a `trust` to `casc`
        Raises `KeyError` if the vouching key is already present in the cascade,
            unless `overwrite` is true
    '''
    pb = trust[0].public_bytes_raw()
    if (not overwrite) and (pb in casc):
        raise KeyError('Refusing to overwrite a trust already present in the cascade when overwrite is false')
    casc[pb] = trust
def add(casc: Types.Cascade, voucher: Types.VoucherPrK, vouchee: Types.Vouchee, *, overwrite: bool = False):
    '''
        Generates a new trust and adds it to `casc`
        Raises `KeyError` if the vouching key is already present in the cascade,
            unless `overwrite` is true
    '''
    add_trust(casc, gen_trust(voucher, vouchee), overwrite=overwrite)
### Removing
def pop(casc: Types.Cascade, voucher: Types.Voucher) -> Types.Trust:
    '''Removes and returns a trust from `casc`'''
    casc.pop(voucher.public_bytes_raw())
### Executing
def walk(casc: Types.Cascade, from_: Types.Voucher) -> typing.Generator[Types.Trust, None, None]:
    '''Walks `casc`, starting at `from_` and yielding trusts in a chain'''
    k = from_
    while (kb := k.public_bytes_raw()) in casc:
        yield casc[kb]
        k = casc[kb][1]
def execute(casc: Types.Cascade, from_: Types.Voucher, to: Types.Vouchee, *, sane_check: bool = True):
    '''
        Walks `casc`, starting at `from_` and verifying trusts in the chain until `to` is reached
        Raises exceptions whenever a failure is encountered
        If `sane_check` is true, then the keys of the cascade are check to ensure that they match the trusts
    '''
    seen = set()
    for trust in walk(casc, from_):
        if id(trust) in seen:
            raise Exception(f'Cascade execption detected a circular cascade at {id(trust)} and refused to continue')
        seen.add(id(trust))
        if sane_check and (casc.get(trust[0].public_bytes_raw(), None) is not trust):
            raise Exception(f'Cascade execution detected an insane cascade at {id(casc[trust[0].public_bytes_raw()])} / {id(trust)} and refused to continue')
        if not run_trust(trust, no_exc=True):
            raise Exception(f'Cascade execution failed to verify trust at {id(trust)}')
        if to == trust[1]: return # success
    raise Exception(f'Cascade execution reached end of chain at {id(trust)}')
