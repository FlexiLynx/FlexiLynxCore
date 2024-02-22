#!/bin/python3

'''Provides utilities for (but not exclusively for) generation of `Blueprint`s'''

#> Imports
import typing
import hashlib
import multiprocessing.pool
from pathlib import Path

from . import parts
from .blueprint import Blueprint

from FlexiLynx.core.util import hashtools
from FlexiLynx.core.util.functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('hash_files', 'make_manifest')

@defaults(hashtools.hash_files)
def hash_files(root: Path, files: typing.Sequence[str], *, max_threads: int = DEFAULT, hash_method: str = DEFAULT) -> dict[str, bytes]:
    '''Hashes a set of files, prepending them with `root`'''
    paths = {root/f: f for f in files}
    return {paths[p]: h for p,h in hashtools.hash_files(*paths.keys(), max_threads=max_threads, hash_method=hash_method).items()}

@defaults(hash_files)
def make_manifest(url: str | None, *files: Path, root: Path = Path('.'), max_threads: int = DEFAULT, hash_method: str = DEFAULT) -> parts.Manifest:
    '''Creates a manifest from a set of files, relative to `root`'''
    return parts.Manifest(url=url, hash_method=hash_method,
                          files=hash_files(root, tuple((f.relative_to(root).as_posix() for f in files)),
                                           max_threads=max_threads, hash_method=hash_method))
