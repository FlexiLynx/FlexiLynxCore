#!/bin/python3

'''Supplies the `Package` class'''

#> Imports
import typing
from pathlib import Path

from .generate import hash_files
from .blueprint import Blueprint

import FlexiLynx
#</Imports

#> Header >/
__all__ = ('Package',)

logger = FlexiLynx.core.logger.getChild('BP')

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
        mismatching = {f for f,h in hash_files(at, files, max_processes=max_processes, hash_method=draft.hash_method).items() if draft.files[f] != h}
        # Return
        return (files - mismatching, mismatching, missing)
    def uninstall(self, draft: str | None = None, *, at: Path = Path('.')):
        '''Uninstalls files on the system, renaming any modified files to protect against accidental deletion'''
        match,mism,miss = self.scan(draft, at=at)
        match = sorted(match); mism = sorted(mism); miss = sorted(miss)
        logger.info(f'Uninstall issued: {self.blueprint.id}{"" if draft is None else f"@{draft}"}')
        if not (miss or mism or match):
            logger.error('Does not appear to be installed? Skipping')
            return
        if miss: logger.error(f'Cannot uninstall missing files:\n - {"\n - ".join(miss)}')
        if mism: logger.warning(f'Changed files will not be removed, but will be renamed:\n - {"\n - ".join(mism)}')
        if match: logger.warning(f'Files will be removed:\n - {"\n - ".join(match)}')
        for p in map(at.__truediv__, mism):
            logger.verbose(f'Moving {p} -> {p}.old')
            p.with_suffix(f'{p.suffix}.old').write_bytes(p.read_bytes())
            logger.trace(f'Unlinking {p}')
            p.unlink()
        clean = set()
        for p in map(at.__truediv__, match):
            logger.verbose(f'Unlinking {p}')
            p.unlink()
            clean.add(p.parent)
        # Clean missing paths
        for p in sorted((p for p in clean), key=lambda p: (len(p.parts), p), reverse=True):
            # If it has anything under it, then continue; otherwise, rmdir it!
            try: next(p.iterdir())
            except StopIteration: pass
            else: continue
            p.rmdir()
            logger.verbose('Removed empty directory {p}')
