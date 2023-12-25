#!/bin/python3

#> Imports
import sys
import time
import hashlib
import base64
import typing
from pathlib import Path
from types import ModuleType
from dataclasses import dataclass
from functools import reduce
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK

from .ManifestCore import Manifest
from .ManifestTypes import *
#</Imports

#> Header >/
__all__ = ('find_tree', 'hash_tree', 'FilePack', 'autogen_manifest')

def find_tree(root: Path, sort_func: typing.Callable[[Path], typing.Any] = lambda p: p.parts,
              include_glob: tuple[str, ...] = ('**/*',),
              exclude_glob: tuple[str, ...] = ('__pycache__/**', 'MANIFEST.*'),
              include_func: typing.Callable[[Path], bool] = lambda p: p.is_file()) -> tuple[Path]:
    return sorted(
        sum((tuple(p.relative_to(root) for p in root.glob(ig)
                   if (not any(p.match(eg) for eg in exclude_glob)) and include_func(p))
             for ig in include_glob), start=()),
        key=sort_func,
    )
def hash_tree(root: Path, tree: tuple[Path], algorithm: typing.Literal[*hashlib.algorithms_available], pack: str | None = None) -> Manifest_contentdata:
    return Manifest_contentdata({f.as_posix() if pack is None else f'{pack}@{f.as_posix()}':
                                 hashlib.new(algorithm, (root/f).read_bytes()).digest() for f in tree})

@dataclass(frozen=True, kw_only=True, slots=True)
class FilePack:
    '''Holds data necessary to find "packs" of files for passing to `autogen_manifest()`'''
    root: Path
    include_glob: tuple[str, ...] = ('*', '**/*',)
    exclude_glob: tuple[str, ...] = ('__pycache__/**', 'MANIFEST.*')
    include_func: typing.Callable[[Path], bool] = lambda p: p.is_file()
    sort_func: typing.Callable[[Path], typing.Any] = lambda p: p.parts
    def render(self, packname: str | None = None, hash_algorithm: typing.Literal[*hashlib.algorithms_available] = 'sha1') -> Manifest_contentdata:
        return hash_tree(self.root, find_tree(self.root, self.sort_func, self.include_glob, self.exclude_glob, self.include_func),
                         algorithm=hash_algorithm, pack=packname)
def autogen_manifest(*, id: str, type_: typing.Literal['module', 'plugin', 'other'],
                     name: str, by: str, desc: str | None = None, contact: str | None = None,
                     key: EdPrivK | Path | None, do_sign: bool = True,
                     files: FilePack, packs: tuple[FilePack, ...] | None = None,
                     manifest_upstream: str, file_upstream: str,
                     hash_algorithm: typing.Literal[*hashlib.algorithms_available] = 'sha1',
                     byte_encoding: typing.Literal[*set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode')] = 'b85',
                     meta_version: str | None = None,
                     min_python_version: tuple[int, int, int] | None = sys.version_info[:3],
                     before: set[str] | None = None, after: set[str] | None = None, requires: set[str] | None = None) -> Manifest:
    '''Automatically generates and signs a Manifest with the given parameters'''
    if do_sign:
        key = EdPrivK.from_private_bytes(key.read_bytes()) if isinstance(key, Path) else key
    crtime = round(time.time()); pcrtime = time.ctime(crtime)
    m = Manifest(id=id, real_version=0, type=type_, format_version=0,
                 upstream=Manifest_upstream(manifest=manifest_upstream, files=file_upstream),
                 crypt=Manifest_crypt(signature=None, public_key=key.public_key() if do_sign else None),
                 version=Manifest_version(meta_version=meta_version, last_update_time=crtime, last_update_time_pretty=pcrtime,
                                          first_creation_time=crtime, first_creation_time_pretty=pcrtime),
                 metadata=Manifest_metadata(name=name, desc=desc, by=by, contact=contact),
                 relatedepends=Manifest_relatedepends(min_python_version=min_python_version, python_implementation=sys.implementation.name, platform=sys.platform,
                                                      before=before, after=after, requires=requires),
                 contentinfo=Manifest_contentinfo(use_packs=(packs is None), skip_files=None),
                 contentdata=Manifest_contentdata(files.render(None, hash_algorithm) | (reduce(dict.__or__, (pk.render(pn) for pn,pk in packs.items())) if packs else {})))
    if do_sign: m.sign(key)
    return m
