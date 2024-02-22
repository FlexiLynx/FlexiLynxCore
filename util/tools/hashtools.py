#!/bin/python3

'''Common utilities for working with hashing algorithms'''

#> Imports
import typing
import hashlib
import multiprocessing.pool
from pathlib import Path
from functools import partial

from .functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('ALGORITHM_DEFAULT_LOW', 'ALGORITHM_DEFAULT_HIGH',
           'TAlgorithmsGuaranteed', 'TAlgorithmsAvailable',
           'hash_many', 'hash_file', 'hash_files')

# Constants
ALGORITHM_DEFAULT_LOW = 'sha1'
ALGORITHM_DEFAULT_HIGH = 'sha512'

# Types
TAlgorithmsGuaranteed = typing.Literal[*hashlib.algorithms_guaranteed]
TAlgorithmsAvailable = typing.Literal[*hashlib.algorithms_available]

# Functions
def hash_many(*datas: bytes, max_threads: int = 8, hash_method: str = ALGORITHM_DEFAULT_HIGH) -> tuple[bytes, ...]:
    '''Hashes multiple sets of bytes using multithreading'''
    procs = min(len(datas), max_threads)
    hfunc = lambda b: hashlib.new(hash_method, b).digest()
    if procs < 2: return tuple(map(hfunc, datas))
    with multiprocessing.pool.ThreadPool(procs) as mp:
        return tuple(mp.map(hfunc, datas))
@defaults(hash_many)
def hash_file(file: Path | str, hash_method: str = DEFAULT) -> bytes:
    '''Opens and hashes a single `Path` (or string coerced into a `Path`)'''
    if not isinstance(file, Path): file = Path(file)
    with file.open('rb') as f:
        return hashlib.file_digest(f, hash_method).digest()
@defaults(hash_many)
def hash_files(*files: Path | str, max_threads: int = DEFAULT, hash_method: str = DEFAULT) -> dict[Path | str, bytes]:
    '''
        Opens and hashes multiple `Path`s (or strings coerced into `Path`s) using multithreading
            Note that, in the returned `dict`, keys that were strings will remain strings
    '''
    paths = tuple(map(Path, files))
    procs = min(len(paths), max_threads)
    if procs < 2: return dict(zip(files, map(partial(hash_file, hash_method=hash_method), paths)))
    with multiprocessing.pool.ThreadPool(procs) as mp:
        return dict(zip(files, mp.map(partial(hash_file, hash_method=hash_method), paths)))
