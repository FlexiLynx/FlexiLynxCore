#!/bin/python3

#> Imports
import io
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
__all__ = ('is_insane', 'render_info',
           'try_load_manifest', 'fetch_upstream', 'verify_upstream',
           'ManifestDiff',
           'update', 'install', 'uninstall')

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
def verify_upstream(local: Manifest, upstream: Manifest):
    # Check upstream signature
    mlogger.warning('Checking upstream manifest against its own signature')
    if not upstream.verify():
        raise InvalidSignature('Upstream manifest failed verification')
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

# Manifest diffs
class ManifestDiff:
    __slots__ = ('local', 'upstream')

    def __init__(self, local: Manifest, upstream: Manifest):
        self.local = local
        self.upstream = upstream
    def __str__(self) -> str:
        with io.StringIO() as sio:
            # <top>
            for k in ('id', 'real_version', 'type', 'format_version'):
                if (l := getattr(self.local, k)) != (u := getattr(self.upstream, k)):
                    sio.write(f'{k}: {l!r} -> {u!r}\n')
            # upstream
            for k,l in self.local.upstream._dict_().items():
                if l != (u := getattr(self.upstream.upstream, k)):
                    sio.write(f'upstream.{k}: {l!r} -> {u!r}\n')
            # crypt
            for k in ('hash_algorithm', 'byte_encoding'):
                if (l := getattr(self.local.crypt, k)) != (u := getattr(self.upstream.crypt, k)):
                    sio.write(f'crypt.{k}: {l!r} -> {u!r}\n')
            if (l := self.local.crypt.signature) != (u := self.upstream.crypt.signature):
                sio.write(f'crypt.signature: {self.local.crypt._encode_(l)} -> {self.upstream.crypt._encode_(u)}\n')
            if (l := self.local.crypt.public_key) != (u := self.upstream.crypt.public_key):
                sio.write(f'crypt.public_key: {self.local.crypt._encode_(l.public_bytes_raw())} -> {self.upstream.crypt._encode_(u.public_bytes_raw())}\n')    
            ## crypt.key_remap_cascade
            lkrcd = self.local.crypt.key_remap_cascade
            ukrcd = self.upstream.crypt.key_remap_cascade
            krcd = self.dict_diff(lkrcd or {}, ukrcd or {})
            if any(krcd):
                sio.write('crypt.key_remap_cascade:\n')
                for a in krcd[0]: sio.write(f' + {a} -> {ukrcd[a]}\n')
                for r in krcd[1]: sio.write(f' - {r} -> {lkrcd[r]}\n')
                for c in krcd[2]: sio.write(f'   {c}: {lkrcd[c]} -> {ukrcd[c]}\n')
            # metadata
            for k,l in self.local.metadata._dict_().items():
                if l != (u := getattr(self.upstream.metadata, k)):
                    sio.write(f'metadata.{k}: {l!r} -> {u!r}\n')
            # relatedepends
            if (l := self.local.relatedepends.min_python_version) != (u := self.upstream.relatedepends.min_python_version):
                sio.write(f'relatedepends.min_python_version: {"<not specified>" if l is None else ".".join(l)} -> {"<not specified>" if u is None else ".".join(u)}\n')
            for k in ('python_implementation', 'platform'):
                if (l := getattr(self.local.relatedepends, k)) != (u := getattr(self.upstream.relatedepends, k)):
                    sio.write(f'relatedepends.{k}: {l!r} -> {u!r}\n')
            for k in ('before', 'after', 'requires'):
                setd = self.set_diff(set(getattr(self.local.relatedepends, k) or set()), set(getattr(self.upstream.relatedepends, k) or set()))
                if any(setd): sio.write(f'relatedepends.{k}:\n')
                for a in setd[0]: sio.write(f' + {a}\n')
                for r in setd[1]: sio.write(f' - {r}\n')
            # contentinfo
            if (l := getattr(self.local.relatedepends, 'use_packs', None)) != (u := getattr(self.upstream.relatedepends, 'use_packs', None)):
                sio.write(f'relatedepends.use_packs: {l!r} -> {u!r}\n')
            setd = self.set_diff(set(getattr(self.local.relatedepends, 'skip_files', None) or set()), set(getattr(self.upstream.relatedepends, 'skip_files', None) or set()))
            if any(setd):
                sio.write('relatedepends.skip_files:\n')
                for a in setd[0]: sio.write(f' + {a}\n')
                for r in setd[1]: sio.write(f' - {r}\n')
            # finalize
            return sio.getvalue().rstrip()

    @staticmethod
    def dict_diff(a: dict, b: dict) -> tuple[tuple[typing.Hashable, ...], tuple[typing.Hashable, ...], tuple[typing.Hashable, ...]]:
        '''Diffs a and b, result: ((<a - b>), (<b - a>), (<changes from a to b>))'''
        return (tuple(b.keys() - a.keys()),
                tuple(a.keys() - b.keys()),
                tuple(k for k,v in b.items() if (k in b) and (b[k] != v)))
    @staticmethod
    def set_diff(a: set, b: set) -> tuple[tuple[typing.Hashable, ...], tuple[typing.Hashable, ...]]:
        '''Diffs a and b, result: ((<a - b>), (<b - a>))'''
        return (tuple(b - a), tuple(a - b))

# Actual manifest execution
## Manifest update
def update(local: Manifest, upstream: Manifest | None = None) -> Manifest:
    '''Updates a manifest'''
    if upstream is None: upstream = fetch_upstream(local)
    print(ManifestDiff(local, upstream))
## [un]Installation
def install(man: Manifest, root: Path = Path.cwd(), *, pack: str | None = None, dry_run: bool = False):
    ...
def uninstall(man: Manifest, root: Path = Path.cwd(), *,
              pack: str | None = None, interactive: bool = True, ensure_all_installed: bool = True,
              dry_run: bool = False):
    '''
        Uninstalls a given Manifest

        Note that if `pack` is given, the "root" (not part of a pack) content is not uninstalled
    '''
    use_pack = pack is not None
    assert (not use_pack) or man.contentinfo.use_packs, 'Cannot specify a pack when packs are not used by this manifest'
    def rm(p: Path):
        if interactive and input(f'Unlink {p} ? (Y/n) >').lower().startswith('n'): return
        mlogger.warning(f'Unlinking {p}')
        if dry_run: print(f'<dry_run> unlink {p}')
        else: p.unlink()
    # Get a list of files to remove
    # note: the following line makes some use of the property of booleans as integers, where False resolves to 0 and True resolves to 1
    # `k.split('@', 1)[1]` if use_pack else `k.split('@', 0)[0]` (resolves to `k`)
    to_rm = sorted({root / p.split('@', use_pack)[use_pack]
                    for p,h in man.contentdata.items() if (
                        (('@' in p) and (p.split('@', 1)[0] == pack)) if use_pack
                        else ('@' not in p))})
    # Ensure that all files to remove are already installed (if needed)
    if ensure_all_installed:
        if not_found := tuple(f for f in to_rm if not f.is_file()):
            raise FileNotFoundError(tuple(f.as_posix() for f in not_found))
    # Remove files
    for f in to_rm:
        if f.is_file(): rm(f)
        else: (print if interactive else mlogger.warning)(f'Skipping {f} (it doesn\'t exist or is not a file)')
    # Check for empty dirs
    for p in {f.parent for f in to_rm if f.parent.is_dir()}:
        if not tuple(p.iterdir()): rm(p)
