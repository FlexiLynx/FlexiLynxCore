#!/bin/python3

#> Imports
import sys
import warnings
import base64, hashlib
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from . import ManifestTypes as mtypes
from .ManifestCore import Manifest
#</Imports

#> Header >/
def is_insane(m: Manifest, fail_on_unsupported_version: bool = True):
    '''
        Checks a manifest for any defects or inconsistencies
            This includes verification
        Throws a:
            `AttributeError` if fields are missing
            `cryptography.exceptions.InvalidSignature` if verification fails
            `TypeError` if the manifest is of an unknown type
            `NotImplementedError` if the byte encoding or hashing algorithm are not supported
            `RuntimeError` if the manifest does not support the current version (UserWarning if fail_on_unsupported_version is False)
            `UserWarning` if the manifest does not support the current Python implementation or system platform
    '''
    # Verify
    if not m.verify():
        raise InvalidSignature('Manifest verification failed')
    # Check type
    if not m.type in {'module', 'plugin', 'other'}:
        raise TypeError(f'Manifest is of an unknown type "{m.type}"')
    # Check support
    if not (he := m.crypt.hash_algorithm) in hashlib.algorithms_available:
        raise NotImplementedError(f'Manifest speaks of an unknown hashing algorithm "{he}"')
    if not (be := m.crypt.byte_encoding) in set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode'):
        raise NotImplementedError(f'Manifest encodes bytes in an unknown format "{be}"')
    # Check version
    if ((mv := m.relatedepends.min_python_version) is not None) and (cv := sys.version_info[:3]) < m.relatedepends.min_python_version:
        msg = f'Manifest demands a Python version of {".".join(mv)}, but you are running {".".join(cv)}'
        if fail_on_unsupported_version: raise RuntimeError(msg)
        else: warnings.warn(UserWarning(msg))
    # Check implementation and platform
    if (ci := sys.implementation.name) != (ti := m.relatedepends.python_implementation):
        warnings.warn(UserWarning(f'Manifest is designed for Python "{ti}", but you are using "{ci}". Things may not work as intended!'))
    if (cp := sys.platform) != (tp := m.relatedepends.platform):
        warnings.warn(UserWarning(f'Manifest is designed for system "{tp}", but you are using "{cp}". Things may not work as intended!'))
