#!/bin/python3

'''Provides utilities for (but not exclusively for) generation of `Blueprint`s'''

#> Imports
import typing
import hashlib
import multiprocessing.pool
from pathlib import Path

from . import parts
from .blueprint import Blueprint
#</Imports

#> Header >/
__all__ = ('hash_files', 'make_manifest')

def hash_files(root: Path, files: typing.Sequence[str], *, max_processes: int = 8, hash_method: str = 'sha1') -> dict[str, bytes]:
    '''Hashes a set of files, prepending them with `root`'''
    procs = min(len(files), max_processes)
    hfunc = lambda f: (f, hashlib.new(hash_method, (root / f).read_bytes()).digest())
    if procs < 2: return dict(map(hfunc, files))
    with multiprocessing.pool.ThreadPool(procs) as mp:
        return dict(mp.map(hfunc, files))

def make_manifest(url: str | None, *files: Path, root: Path = Path('.'), max_processes: int = 8, hash_method: str = 'sha1') -> parts.Manifest:
    '''Creates a manifest from a set of files, relative to `root`'''
    return parts.Manifest(url=url, hash_method=hash_method,
                          files=hash_files(root, tuple((f.relative_to(root).as_posix() for f in files)),
                                           max_processes=max_processes, hash_method=hash_method))
