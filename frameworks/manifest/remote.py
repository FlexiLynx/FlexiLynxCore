#!/bin/python3

#> Imports
import typing
from pathlib import Path
from urllib import request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from . import executor
from .core import Manifest, load_packed, load_json, load_ini, load_to_render
from .exceptions import *

from FlexiLynx import logger
#</Imports

#> Header >/
__all__ = ('fetch_upstream', 'verify_upstream', 'self_update')

mlogger = logger.getChild('core.fw.manifests')

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
    return executor.try_load_manifest(data, order)[1]
def verify_upstream(local: Manifest, upstream: Manifest):
    # Check upstream signature
    mlogger.warning('Checking upstream manifest against its own signature')
    if not upstream.verify():
        raise CrossInvalidSignatureError(local, upstream, 'Upstream manifest failed verification')
    # Handle cascades
    if local.crypt.public_key != upstream.crypt.public_key:
        mlogger.warning('Upstream crypt.public_key differs from local, entering cascade')
        upstream.chk_cascade(upstream.crypt.public_key, local.crypt.public_key, debug_callback=lambda type_, vals: mlogger.info({
            'check': 'Entering cascade with %s, looking for {}',
            'match': 'Key {} is trustworthy through cascade',
            'found': 'Checking next key in cascade: {}',
            'verify': '{0} cascades to {2}',
        }[type_].format(*(local.crypt._encode_(v.public_bytes_raw() if isinstance(v, EdPubK) else v) for v in vals))))
        mlogger.info('Cascade accepted: new public key %s is trusted', local.crypt._encode_(upstream.crypt.public_key.public_bytes_raw()))

def self_update(local: Manifest, upstream: Manifest | None = None, *, print_diff: bool = True, auth: bool = True) -> Manifest:
    '''Updates a manifest'''
    if upstream is None: upstream = fetch_upstream(local)
    if print_diff: print(executor.ManifestDiff(local, upstream))
    if auth:
        mlogger.warning('Authenticating upstream manifest')
        verify_upstream(local, upstream)
    return upstream
