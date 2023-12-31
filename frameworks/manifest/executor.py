#!/bin/python3

#> Imports
import io
import sys
import time
import traceback
import warnings
import base64, hashlib
import typing
import multiprocessing
from pathlib import Path
from functools import partial
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK

from .core import Manifest
from .exceptions import *

from FlexiLynx import logger
from FlexiLynx.core.ffetch import fancy_fetch
#</Imports

#> Header >/
__all__ = ('is_insane', 'render_info', 'get_content',
           'try_load_manifest',
           'ManifestDiff', 'ContentDiff',
           'install', 'uninstall')

mlogger = logger.getChild('core.fw.manifests')

# Helper functions
def is_insane(m: Manifest, fail_on_unsupported_version: bool = True):
    '''
        Checks a manifest for any defects or inconsistencies
            This includes verification
        Throws a:
            `AttributeError` if fields are missing
            `InsaneSignatureError` if verification fails
            `UnknownTypeError` if the manifest is of an unknown type
            `OtherRelationsError` if the manifest is of "other" type but specifies relatedepends fields "before", "after", and/or "requires"
            `UnknownHashAlgorithmError`/`UnknownByteEncodingError` if the byte encoding or hashing algorithm are not supported
            `UnsupportedVersionError` if the manifest does not support the current version (UserWarning if fail_on_unsupported_version is False)
            `TimeTravelError` if the manifest's last update time is before its first creation time
            `UserWarning` if the manifest does not support the current Python implementation or system platform
    '''
    # Verify
    if not m.verify():
        raise InsaneSignatureError(m, 'Manifest verification failed')
    # Check type
    if not m.type in {'module', 'plugin', 'other'}:
        raise UnknownTypeError(m, f'Manifest is of an unknown type "{m.type}"')
    if m.type == 'other':
        if fields := tuple(f for f in ('before', 'after', 'requires') if getattr(m.relatedepends, f)):
            raise OtherRelationsError(m, f'Manifest is of type "other", but illegally specifies "{", ".join(fields)}" in relatedepends')
    # Check support
    if not (he := m.crypt.hash_algorithm) in hashlib.algorithms_available:
        raise UnknownHashAlgorithmError(m, he, f'Manifest speaks of an unknown hashing algorithm "{he}"')
    if not (be := m.crypt.byte_encoding) in set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode'):
        raise UnknownByteEncodingError(m, be, f'Manifest encodes bytes in an unknown format "{be}"')
    # Check version
    if ((mv := m.relatedepends.min_python_version) is not None) and (cv := sys.version_info[:3]) < mv:
        msg = f'Manifest demands a Python version of {".".join(mv)}, but you are running {".".join(cv)}'
        if fail_on_unsupported_version: raise UnsupportedVersionError(m, mv, msg)
        else: warnings.warn(UserWarning(msg))
    # Check time
    if (delta := (m.version.first_creation_time - m.version.last_update_time)) > 1: # allow a buffer of 1 sec
        raise TimeTravelError(m, delta, f'Manifest was apparently last updated {delta} seconds before its original creation')
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

def get_content(m: Manifest, root: Path = Path('.'), pack: str | None = None) -> typing.Iterator[tuple[Path, bytes]]:
    '''
        Extracts content-data from a manifest
        Resolves packs as needed and respects skip_files

        Returns an iterator of (path, hash)
    '''
    use_pack = pack is not None
    if not m.contentinfo.use_packs:
        if use_pack:
            raise PacksDisabledError(m, 'Cannot specify a pack when packs are not used by this manifest')
        return ((root/f, h) for f,h in m.contentdata.items())
    # note: in `f.split('@', use_pack)[use_pack]`, use_pack is used as an integer
    return ((root / f, h) for f,h in (
        (f.split('@', use_pack)[use_pack], h) for f,h in m.contentdata.items()
        if ((use_pack and (f.split('@', 1)[0] == pack)) if ('@' in f) else not use_pack)
    ) if f not in m.contentdata.skip_files)

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
    raise CorruptedFileError('All handlers failed to load the manifest', data=data)

# Manifest diffs
class _DiffBase:
    __slots__ = ()
    @classmethod
    def dict_diff(cls, a: dict, b: dict, show_value: bool = True) -> typing.Generator[str, None, None]:
        '''Yields a string diff of two dicts'''
        for add in (b.keys() - a.keys()): yield f' + {cls.render_item(add)}'
        for rem in (a.keys() - b.keys()): yield f' - {cls.render_item(rem)}'
        for chg in (k for k,v in a.items() if (k in b) and (b[k] != v)):
            yield f'   {cls.render_item(chg)}: {f"{cls.render_item(a[chg])} -> {cls.render_item(b[chg])}" if show_value else "<changed>"}'
    @classmethod
    def set_diff(cls, a: set, b: set) -> typing.Generator[str, None, None]:
        '''Yields a string diff of two sets'''
        for add in (b - a): yield f' + {cls.render_item(add)}'
        for rem in (a - b): yield f' - {cls.render_item(rem)}'

    @classmethod
    def render_item(cls, o: typing.Any) -> str:
        '''Renders an object (that would normally be in a Manifest) as a string'''
        match o:
            case set() | frozenset():
                if not o: return 'set()'
                return f'{{{", ".join(cls.render_item(i) for i in o)},}}'
            case tuple() | list():
                if not o: return '()'
                return f'({{", ".join(cls.render_item(i) for i in o)}},)'
            case EdPubK(): return cls.render_item(o.public_bytes_raw())
            case bytes(): return base64.b85encode(o).decode()
            case Path(): return o.as_posix()
            case (None): return '<not specified>'
        return repr(o)
class ManifestDiff(_DiffBase):
    __slots__ = ('local', 'upstream')

    def __init__(self, local: Manifest, upstream: Manifest):
        self.local = local
        self.upstream = upstream

    def __str__(self) -> str:
        with io.StringIO() as sio:
            # <top>
            for k in ('id', 'real_version', 'type', 'format_version'):
                self.diffof(sio, k)
            # upstream
            for k in self.local.upstream._dict_().keys():
                self.diffof(sio, f'upstream.{k}')
            # crypt
            for k in ('signature', 'public_key', 'hash_algorithm', 'byte_encoding', 'key_remap_cascade'):
                self.diffof(sio, f'crypt.{k}')
            # metadata
            for k in self.local.metadata._dict_().keys():
                self.diffof(sio, f'metadata.{k}')
            # relatedepends
            if (l := self.local.relatedepends.min_python_version) != (u := self.upstream.relatedepends.min_python_version):
                sio.write(f'relatedepends.min_python_version: {"<not specified>" if l is None else ".".join(l)} -> {"<not specified>" if u is None else ".".join(u)}\n')
            for k in ('python_implementation', 'platform', 'before', 'after', 'requires'):
                self.diffof(sio, f'relatedepends.{k}')
            # contentinfo
            for k in ('use_packs', 'skip_files'):
                self.diffof(sio, f'contentinfo.{k}')
            # contentdata
            self.diffof(sio, 'contentdata')
            # finalize
            return sio.getvalue().rstrip()

    def diffof(self, sio: typing.TextIO, attr: str):
        '''Runs a diff of an `attr` in `self.local` and `self.upstream` and writes it to `sio`'''
        assert attr.count('.') < 2
        sp = attr.split('.')
        a = getattr(self.local, sp[0], None)
        b = getattr(self.upstream, sp[0], None)
        if len(sp) == 2:
            a = getattr(a, sp[1], None)
            b = getattr(b, sp[1], None)
        if (a == b) or (bool(a) == bool(b)): return
        sio.write(f'{attr}:')
        if isinstance(a, dict) or isinstance(b, dict):
            for s in self.dict_diff(a or {}, b or {}):
                sio.write('\n')
                sio.write(s)
        elif isinstance(a, dict) or isinstance(b, dict):
            for s in self.set_diff(a or set(), b or set()):
                sio.write('\n')
                sio.write(s)
        else:
            sio.write(f' {self.render_item(a)} -> {self.render_item(b)}\n')
class ContentDiff(_DiffBase):
    __slots__ = ('man',)

    def __init__(self, man: Manifest):
        self.man = man

    def __str__(self) -> str:
        return self.diff[0]
    def diff(self, root: Path = Path('.'), pack: str | None = None, *, content: dict[Path, bytes] | None = None, local: dict[Path, bytes] | None = None) -> tuple[str, tuple[Path, ...], tuple[Path, ...]]:
        c = dict(get_content(self.man, root, pack)) if content is None else content
        l = self.hash_files(self.man.crypt.hash_algorithm, tuple(f for f in c.keys() if f.is_file())) if local is None else local
        return ('\n'.join(self.dict_diff(l, c)), tuple(c.keys()-l.keys()), tuple(f for f,h in l.items() if h != c[f]))
    __str__ = diff

    @staticmethod
    def _hash_file(algorithm: typing.Literal[*hashlib.algorithms_available], file: Path | bytes) -> tuple[Path | bytes, bytes]:
        return (file, hashlib.new(algorithm, (file.read_bytes() if isinstance(file, Path) else file)).digest())
    @classmethod
    def hash_files(cls, algorithm: typing.Literal[*hashlib.algorithms_available], files: tuple[Path | bytes, ...], *, max_processes: int = multiprocessing.cpu_count() * 2) -> dict[Path | bytes, bytes]:
        '''Hashes a tuple of files'''
        h = partial(cls._hash_file, algorithm)
        processes = min(len(files), max_processes)
        if processes < 2:
            return dict(map(h, files))
        with multiprocessing.Pool(processes) as mp:
            return dict(mp.map(h, files))

# [un]Installation
def install(man: Manifest, root: Path = Path.cwd(), *, pack: str | None = None, dry_run: bool = False, interactive: bool = True) -> bool | None:
    '''
        Installs a given manifest

        Note that if `pack` is given, the "root" (not part of a pack) content is not installed
    '''
    content = dict(get_content(man))
    local = ContentDiff.hash_files(man.crypt.hash_algorithm, tuple(f for f in content.keys() if f.is_file()))
    strdiff, new, updated = ContentDiff(man).diff(root, pack, content=content, local=local)
    print(strdiff)
    if interactive and input(f'Fetch specified files{f" ({len(updated)} replaced files)" if updated else ""}? (Y/n) >').lower().startswith('n'):
        return False
    mhashes = {f: content[f] for f in new+updated}
    files = {f: fancy_fetch(f'{man.upstream.files}/{f}') for f in mhashes.keys()}
    if not files:
        print('Nothing to do')
        return None
    print(f'Checking hashes of {len(files)} file(s)')
    rfiles = {c: f for f,c in files.items()}
    fhashes = {rfiles[c]: h for c,h in ContentDiff.hash_files(man.crypt.hash_algorithm, rfiles.keys()).items()}
    if mhashes == fhashes: print('Fetched files\' hashes match manifest content')
    else:
        print(f'Hashes mismatch manifest\'s content:\n{"\n".join(ContentDiff.dict_diff(mhashes, fhashes, show_value=False))}')
        raise ValueError('Fetched content differs from manifest content')
    return True if interactive else None
    
def uninstall(man: Manifest, root: Path = Path.cwd(), *,
              pack: str | None = None, interactive: bool = True, ensure_all_installed: bool = True,
              dry_run: bool = False):
    '''
        Uninstalls a given Manifest

        Note that if `pack` is given, the "root" (not part of a pack) content is not uninstalled
    '''
    def rm(p: Path):
        if interactive and input(f'Unlink {p} ? (Y/n) >').lower().startswith('n'): return
        mlogger.warning(f'Unlinking {p}')
        if dry_run: print(f'<dry_run> unlink {p}')
        else: p.unlink()
    to_rm = tuple(f for f,h in get_content(man, root, pack))
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
