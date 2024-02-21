#!/bin/python3

'''Supplies the `Package` class'''

#> Imports
import typing
from pathlib import Path

from .generate import hash_files
from .blueprint import Blueprint

import FlexiLynx
from FlexiLynx.core.util import hashtools
from FlexiLynx.core.util.net import fetchx
#</Imports

#> Header >/
__all__ = ('Package',)

logger = FlexiLynx.core.logger.getChild('BP')

class Package:
    '''Represents a package that may or may not be on the system; built from a `Blueprint`'''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

    def scan(self, draft: str | None = None, *, at: Path = Path('.'), max_threads: int = 8) -> tuple[frozenset[Path], frozenset[Path], frozenset[Path]]:
        '''
            Checks for missing or mismatching (changed) artifacts on the local system
            Returns a tuple of frozensets, in the following order: (`matching`, `mismatching`, `missing`)
            A `draft` of `None` selects the "main" files
            `max_threads` is the limit of processes in the multiprocessing pool for hashing files
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
        mismatching = {f for f,h in hash_files(at, files, max_threads=max_threads, hash_method=draft.hash_method).items() if draft.files[f] != h}
        # Return
        return (files - mismatching, mismatching, missing)

    def install(self, draft: str | None = None, *, at: Path = Path('.'), needed: bool = True, resilient: bool = False, max_threads: int = 8,
                fetchfn: typing.Callable[[str, ...], typing.Sequence[bytes]] = fetchx, **fetch_args) -> bool | None:
        '''
            Installs files on the system, only downloading needed files if `needed` is true
            Raises `ValueError` if any downloaded files fail verification,
                unless `resilient` is true, in which case files that pass verification will match,
                a `critical` logging will be issued, and `True` will be returned
        '''
        match,mism,miss = self.scan(draft, at=at)
        match = tuple(sorted(match)); mism = tuple(sorted(mism)); miss = tuple(sorted(miss))
        logger.terse(f'Install issued: {self.blueprint.id}{"" if draft is None else f"@{draft}"}')
        if match:
            logger.verbose(f'Some files are already installed:\n - {"\n - ".join(match)}')
            if not needed:
                logger.warning(f'`needed` is set to false -- up-to-date file(s) will be reinstalled!')
        if not (miss or mism or (match and not needed)):
            logger.terse('Nothing to do -- no install needed')
            return None
        if mism: logger.info(f'{len(mism)} outdated file(s) will need to be upgraded:\n - {"\n - ".join(mism)}')
        if miss: logger.info(f'{len(miss)} new file(s) will need to be installed:\n - {"\n - ".join(miss)}')
        draft = self.blueprint.main if draft is None else self.blueprint.drafts[draft]
        urls = {f: f'{draft.url.rstrip("/")}/{f}' for f in (() if needed else match)+mism+miss}
        logger.verbose(f'The following files will be downloaded:\n - {"\n - ".join(urls)}')
        files = dict(zip(urls.keys(), fetchx(*urls.values())))
        logger.info(f'Downloading complete, calculating hashes of {len(files)} file(s)...')
        hashes = dict(zip(files.keys(), hashtools.hash_many(*files.values(), max_threads=max_threads, hash_method=draft.hash_method)))
        logger.info('Hashing complete')
        mismh = {f: h for f,h in hashes.items() if h != draft.files[f]}
        if mismh:
            if not resilient:
                raise ValueError(f'Some files failed verification: {", ".join(mismh.keys())}')
            logger.critical(f'Some files failed verification, installing verified files anyway! '
                            f'This may cause partial updates and breakage!\nMismatched files: {", ".join(mismh.keys())}')
        for f,d in files.items():
            if f in mismh:
                logger.error(f'Skipping {f}: it failed verification')
                continue
            logger.info(f'Installing {len(d)} byte(s) to {at/f}')
            (at/f).write_bytes(d)
        logger.terse('Installation complete')
        return not not mismh
    def uninstall(self, draft: str | None = None, *, at: Path = Path('.'), clean_pyc: bool = True, clean_empty: bool = True):
        '''Uninstalls files on the system, renaming any modified files to protect against accidental deletion'''
        match,mism,miss = self.scan(draft, at=at)
        match = sorted(match); mism = sorted(mism); miss = sorted(miss)
        logger.terse(f'Uninstall issued: {self.blueprint.id}{"" if draft is None else f"@{draft}"}')
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
        # Clean Python caches
        if clean_pyc:
            for p in tuple(clean):
                if not (p/'__pycache__').exists(): continue
                logger.info(f'Cleaning {p/"__pycache__"}')
                for f in p.glob('*.pyc'):
                    logger.verbose(f'Unlinking {f}')
                    f.unlink()
                clean.add(p/'__pycache__') # remove it later if empty
        # Clean empty paths
        if clean_empty:
            clean = sorted((p for p in clean), key=lambda p: (len(p.parts), p), reverse=False)
            while clean:
                p = clean.pop()
                # If it has anything under it, then continue; otherwise, rmdir it!
                while p.is_relative_to(at) and len(p.parts):
                    try: next(p.iterdir())
                    except StopIteration:
                        p.rmdir()
                        logger.verbose(f'Removed empty directory {p}')
                    p = p.parent
                    if p in clean: break
