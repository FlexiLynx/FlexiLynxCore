#!/bin/python3

#> Imports
import sys
import time
import traceback
import warnings
import base64, hashlib
import typing
from pathlib import Path
from urllib import request
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK

from . import ManifestTypes as mtypes
from .ManifestCore import Manifest, load_packed, load_json, load_ini, load_to_render

from FlexiLynx import logger
#</Imports

#> Header >/
__all__ = ('is_insane', 'render_info', 'try_load_manifest', 'fetch_upstream')

mlogger = logger.getChild('core.fw.manifests')

# Helper functions
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

def render_info(m: Manifest, level: typing.Literal['terse+', 'terse', 'normal', 'verbose']) -> str:
    '''Renders information about a manifest'''
    types = {'other': '', 'plugin': 'Plugin ', 'module': 'Module '}
    i_terse_ = f'{types[m.type]}"{m.metadata.name}"'
    if level == 'terse+': return i_terse_
    i_terse = f'{i_terse_} by {m.metadata.by}'
    if level == 'terse': return i_terse
    i_normal = f'{i_terse}{"" if m.metadata.contact is None else f" ({m.metadata.contact})"}' \
               f'{"" if m.metadata.desc is None else f": {m.metadata.desc}"}'
    if level == 'normal': return i_normal
    time_fmt = '%Y-%m-%dT%H:%M:%S'
    return f'{i_terse}{"" if m.metadata.contact is None else f" ({m.metadata.contact})"}' \
           f'{f" v{m.real_version}" if m.version.meta_version is None else f" [{m.version.meta_version}]"}' \
           f' (as of {time.strftime(time_fmt, time.localtime(m.version.last_update_time))} (first created at {time.strftime(time_fmt, time.localtime(m.version.first_creation_time))}))' \
           f'{"" if m.metadata.desc is None else f"\n {m.metadata.desc}"}' \
           f' for {m.relatedepends.python_implementation}' \
           f'{"" if m.relatedepends.min_python_version is None else f""" {".".join(map(str, m.relatedepends.min_python_version))}"""} on {m.relatedepends.platform}' \
           f'{f"""\ndepends on: {",".join(m.relatedepends.requires)}""" if m.relatedepends.requires else ""}'

# Loading & upstream functions
def try_load_manifest(data: bytes, methods: tuple[typing.Callable[[bytes], Manifest], ...]) -> tuple[typing.Callable[[bytes], Manifest], Manifest]:
    for i,m in enumerate(methods):
        mlogger.verbose('Trying to decode %d byte(s) via %s() (method %d/%d)',
                        len(data), m.__name__, i+1, len(methods))
        try:
            return (m, m(data))
        except Exception as e:
            mlogger.info('Could not decode %d byte(s) via %s(); got %s',
                         len(data), m.__name__, (''.join(traceback.format_exception_only(e))).strip())
    raise TypeError('All handlers failed to load the manifest')
def fetch_upstream(local: Manifest) -> Manifest:
    # Fetch
    mlogger.info('Fetching upstream of "%s" manifest "%s" from %s',
                 local.type, local.metadata.name, local.upstream.manifest)
    with request.urlopen(local.upstream.manifest) as r:
        data = r.read()
    mlogger.verbose('Fetched %d byte(s) from %s',
                    len(data), local.upstream.manifest)
    # (try to) Guess its type and parse it
    suff = Path(local.upstream.manifest).suffix.split('.')[-1].lower()
    order = ((load_json, load_ini, load_packed) if suff == 'json' else
             (load_packed, load_ini, load_json) if suff in {'pak', 'pakd', 'packd', 'packed'} else
             (load_ini, load_json, load_packed))
    mlogger.info('Attempting to decode %d byte(s)', len(data))
    mlogger.verbose(' using methods:\n - %s\n - %s\n - %s', *(m.__name__ for m in order))
    return try_load_manifest(data, order)[1]
