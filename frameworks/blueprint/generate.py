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
__all__ = ('hash_files',)

def hash_files(root: Path, files: typing.Iterable[str], *, max_processes: int = 8, hash_method: str = 'sha1') -> dict[str, bytes]:
    '''Hashes a set of files, prepending them with `root`'''
    procs = min(len(files), max_processes)
    hfunc = lambda f: (f, hashlib.new(hash_method, (root / f).read_bytes()).digest())
    if procs < 2: return dict(map(hfunc, files))
    with multiprocessing.pool.ThreadPool(procs) as mp:
        return dict(mp.map(hfunc, files))
