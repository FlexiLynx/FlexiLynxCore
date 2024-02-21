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
from enum import IntEnum
from types import SimpleNamespace
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
#</Imports

#> Header >/
__all__ = ('Types', 'ExecutionReturn', 'CascadeException', 'CascadeExceptionAtTrust', 'RefusalToOverwriteTrustError',
               'CircularCascadeError', 'InsaneCascadeError', 'VerificationError', 'BrokenCascadeError',
           'gen_trust', 'run_trust',
           'add_trust', 'add', 'pop', 'walk', 'execute')

# Types
## Type-hints
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
## Execution return code
ExecutionReturn = IntEnum('ExecutionReturn', ('SUCCESS', 'CIRCULAR', 'INSANE', 'INVALID_SIGNATURE', 'BROKEN'), start=0)
## Exceptions
class CascadeException(Exception):
    '''
        A generic exception for cascade-related difficulties
        Note that this is only for specifically raised exceptions,
            things like `KeyError` and `InvalidSignature` will not be transformed
    '''
    __slots__ = ('cascade',)
    def __init__(self, *args, cascade: Types.Cascade | None = None, **kwargs):
        self.cascade = cascade
        super().__init__(*args, **kwargs)
class CascadeExceptionAtTrust(CascadeException):
    '''A generic exception for cascade-related difficulties that occur at a specific trust'''
    __slots__ = ('at',)
    def __init__(self, *args, at: int, **kwargs):
        self.at = at
        super().__init__(*args, **kwargs)
class RefusalToOverwriteTrustError(CascadeExceptionAtTrust):
    '''An error for when a trust would be overwritten, but was disallowed'''
    __slots__ = ()
class CircularCascadeError(CascadeExceptionAtTrust):
    '''An error for when a trust would be evaluated twice, meaning that it is part of a circular chain'''
    __slots__ = ()
    CORRESPONDS = ExecutionReturn.CIRCULAR
class InsaneCascadeError(CascadeExceptionAtTrust):
    '''An error for when a trust's vouching key doesn't match the trust itself in the cascade'''
    __slots__ = ()
    CORRESPONDS = ExecutionReturn.INSANE
class VerificationError(CascadeExceptionAtTrust):
    '''An error for when a trust failed verification during cascade execution'''
    __slots__ = ()
    CORRESPONDS = ExecutionReturn.INVALID_SIGNATURE
class BrokenCascadeError(CascadeExceptionAtTrust):
    '''An error for when the end of a chain was reached without finding the target key'''
    __slots__ = ()
    CORRESPONDS = ExecutionReturn.BROKEN

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
        Raises `RefusalToOverwriteTrustError` if the vouching key is already present in the cascade,
            unless `overwrite` is true
    '''
    pb = trust[0].public_bytes_raw()
    if (not overwrite) and (pb in casc):
        raise RefusalToOverwriteTrustError('Refusing to overwrite a trust already present in the cascade when overwrite is false', cascade=casc, at=id(casc[pb]))
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
def execute(casc: Types.Cascade, from_: Types.Voucher, to: Types.Vouchee, *, sane_check: bool = True, return_code: bool = False) -> None | ExecutionReturn:
    '''
        Walks `casc`, starting at `from_` and verifying trusts in the chain until `to` is reached
        Raises exceptions whenever a failure is encountered, or returns an `ExecutionReturn` if `return_code`:
            `CircularCascadeError` / `ExecutionReturn.CIRCULAR` when a trust is seen twice
            `InsaneCascadeError` / `ExecutionReturn.INSANE` when `sane_check` and a trust's vouching key does not match the key in the cascade
            `VerificationError` / `ExecutionReturn.INVALID_SIGNATURE` when a trust fails signature verification
            `BrokenCascadeError` / `ExecutionReturn.BROKEN` when the end of the chain is reached and `to` hasn't been found
        Returns `None` on success, or `ExecutionReturn.SUCCESS` if `return_code`
        If `sane_check` is true, then the keys of the cascade are check to ensure that they match the trusts
    '''
    seen = set()
    for trust in walk(casc, from_):
        if id(trust) in seen:
            if return_code: return ExecutionReturn.CIRCULAR
            raise CircularCascadeError(f'Cascade execption detected a circular cascade at {id(trust)} and refused to continue', cascade=casc, at=id(trust))
        seen.add(id(trust))
        if sane_check and (casc.get(trust[0].public_bytes_raw(), None) is not trust):
            if return_code: return ExecutionReturn.INSANE
            raise InsaneCascadeError(f'Cascade execution detected an insane cascade at'
                                     f'{id(casc[trust[0].public_bytes_raw()])} / {id(trust)} and refused to continue', cascade=casc, at=id(trust))
        if not run_trust(trust, no_exc=True):
            if return_code: return ExecutionReturn.INVALID_SIGNATURE
            raise VerificationError(f'Cascade execution failed to verify trust at {id(trust)}', cascade=casc, at=id(trust))
        if to == trust[1]: return ExecutionReturn.SUCCESS if return_code else None
    if return_code: return ExecutionReturn.BROKEN
    raise BrokenCascadeError(f'Cascade execution reached end of chain at {id(trust)}', cascade=casc, at=id(trust))
