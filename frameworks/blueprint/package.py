#!/bin/python3

'''Supplies the `Package` class'''

#> Imports
import typing
from pathlib import Path

from .generate import hash_files
from .blueprint import Blueprint
#</Imports

#> Header >/
__all__ = ('Package',)

class Package:
    '''Represents a package that may or may not be on the system; built from a `Blueprint`'''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

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
        mismatching = {f for f,h in hash_files(at, files, max_processes=max_processes, hash_method=draft.hash_method).items() if draft[f] != h}
        # Return
        return (files - mismatching, mismatching, missing)
