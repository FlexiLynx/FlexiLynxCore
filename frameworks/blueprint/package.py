#!/bin/python3

'''Supplies the `Package` class'''

#> Imports
import typing
import hashlib
import multiprocessing.pool
from pathlib import Path
from functools import partial

from .blueprint import Blueprint
#</Imports

#> Header >/
__all__ = ('Package',)

class Package:
    '''Represents a package that may or may not be on the system; built from a `Blueprint`'''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

    @staticmethod
    def hash_files(root: Path, files: typing.Iterable[str], *, max_processes: int = 8, hash_method: str = 'sha1') -> dict[str, bytes]:
        '''Hashes a set of files, prepending them with `root`'''
        procs = min(len(files), max_processes)
        hfunc = lambda f: (f, hashlib.new(hash_method, (root / f).read_bytes()).digest())
        if procs < 2: return dict(map(hfunc, files))
        with multiprocessing.pool.ThreadPool(procs) as mp:
            return dict(mp.map(hfunc, files))
    def scan(self, draft: str | None = None, *, at: Path = Path('.'), max_processes: int = 8) -> tuple[frozenset[Path], frozenset[Path], frozenset[Path]]:
        '''
            Checks for missing or mismatching (changed) artifacts on the local system
            Returns a tuple of frozensets, in the following order: (`matching`, `mismatching`, `missing`)
            A `draft` of `None` selects the "main" files
            `max_processes` is the limit of processes in the multiprocessing pool for hashing files
        '''
        draft = self.blueprint.main if draft is None else self.blueprint.drafts[draft]
        files = set(draft.files.keys())
        # Check for missing files
        missing = set()
        for f in draft.files.keys():
            if not (at / f).exists():
                files.remove(f)
                missing.add(f)
        # Check for mismatched files
        mismatching = {f for f,h in self.hash_files(at, files, max_processes=max_processes, hash_method=draft.hash_method).items() if draft[f] != h}
        # Return
        return (files - mismatching, mismatching, missing)
