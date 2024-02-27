#!/bin/python3

'''Supplies the `Package` class'''

#> Imports
import json
import typing
import functools
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from .generate import hash_files
from .blueprint import Blueprint

from . import logger

from FlexiLynx.core.util import Config
from FlexiLynx.core.util import hashtools
from FlexiLynx.core.util.net import fetchx
from FlexiLynx.core.util.functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('Package', 'BaseManagedPackage')

class Package:
    '''Represents a package that may or may not be on the system; built from a `Blueprint`'''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

    @defaults(hash_files)
    def scan(self, draft: str | None = None, *, at: Path = Path('.'), max_threads: int = DEFAULT) -> tuple[frozenset[Path], frozenset[Path], frozenset[Path]]:
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

    @defaults(Blueprint.update)
    def update(self, url: str | None = DEFAULT, *, fetchfn: typing.Callable[[str], bytes] = DEFAULT,
               verify: bool = DEFAULT, verify_self: bool = DEFAULT, key_update: Blueprint.KeyUpdate = DEFAULT):
        '''
            Updates this package's blueprint
                If `url` is not `None`, it overrides the blueprint's `.url`
            See `help(Blueprint.update)` for information on other arguments
        '''
        logger.trace('Issuing update to blueprint through package')
        self.blueprint = self.blueprint.update(url, fetchfn=fetchfn, verify=verify, verify_self=verify_self, key_update=key_update)

    @defaults(hashtools.hash_many)
    def install(self, draft: str | None = None, *, at: Path = Path('.'), needed: bool = True, resilient: bool = False, max_threads: int = DEFAULT,
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
            (at/f).parent.mkdir(parents=True, exist_ok=True)
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

class BaseManagedPackage(Package):
    '''...'''
    __slots__ = ('install_location', 'config', 'drafts', 'files', 'keep', '_save_thread', '_save_condition')

    def __init__(self, install_location: Path):
        self.install_location = install_location
        super().__init__(Blueprint.deserialize((install_location/'blueprint.json').read_text()))
        self.config = Config(install_location/'config.json')
        self.config.load(self.config.path.read_text() if self.config.path.exists() else '{}')
        self.drafts = self.config.get('drafts', [])
        self.files = self.config.get('files', ['blueprint.json', 'config.json'])
        self.keep = self.config.get('keep', ['blueprint.json', 'config.json'])
        self._save_condition = threading.Condition()
        self._save_thread = threading.Thread(target=self._save_loop, daemon=True)
    def _save_loop(self):
        with self._save_condition:
            while True:
                self._save_condition.wait()
                self.config.save()

    def selected_files(self) -> typing.Iterator[str]:
        '''
            Yields all selected files, sourcing from all enabled drafts
            *Will* yield copies if they exist in drafts
        '''
        yield from iter(self.blueprint.main.files.keys())
        if not self.drafts:
            return
        if self.blueprint.drafts is None:
            raise TypeError(f'Cannot select draft {draft!r}, as the blueprint does not support drafts')
        for d in self.drafts:
            yield from iter(self.blueprint.drafts[d].files.keys())
    def upgrade(self):
        '''
            Installs the package in a temporary location, then copies it over,
                additionally removing registered files that are no longer needed
            Drafts, if added, are installed in the order of the `drafts` field
        '''
        logger.trace(f'Upgrade issued for: {self.blueprint.id}')
        cfiles = frozenset(self.files)
        nfiles = frozenset(self.selected_files())
        _to_keep = frozenset(self.keep)
        to_install = (nfiles - cfiles) - _to_keep
        to_remove = (cfiles - nfiles) - _to_keep
        to_replace = (cfiles & nfiles) - _to_keep
        if to_install: logger.terse(f'The following files are selected for installation:\n - {"\n - ".join(sorted(to_install))}')
        if to_replace: logger.warning(f'The following files are selected for removal:\n - {"\n - ".join(sorted(to_remove))}')
        if to_remove: logger.warning(f'The following files are selected for (potential) replacement:\n - {"\n - ".join(sorted(to_replace))}')
        if not (to_install or to_replace or to_remove):
            logger.warning('Nothing to do, upgrade cancelled')
            return
        if to_install or to_replace:
            with TemporaryDirectory() as tmploc:
                tmploc = Path(tmploc)
                logger.verbose(f'Copying registered files that are selected for potential replacement to {tmploc}')
                for f in to_replace:
                    (tmploc/f).parent.mkdir(parents=True, exist_ok=True)
                    (tmploc/f).write_text((self.install_location/f).read_text())
                logger.verbose(f'Installing upgrade for main and {len(self.drafts)} draft(s) to temporary location: {tmploc}')
                self.install(at=tmploc)
                for d in self.drafts:
                    self.install(d, at=tmploc)
                logger.info(f'Upgrade downloaded for: {self.blueprint.id}; clearing current files')
                if to_install:
                    logger.info(f'Copying {len(to_install)} file(s) selected for installation')
                    for f in to_install:
                        logger.verbose(f'Installing {tmploc/f} to {self.install_location/f}')
                        if (self.install_location/f).exists():
                            logger.error(f'File registered as not installed, yet is present on the filesystem: {self.install_location/f}\nRefusing to install')
                            continue
                        (self.install_location/f).parent.mkdir(parents=True, exist_ok=True)
                        logger.trace(f'Copied {(self.install_location/f).write_bytes((tmploc/f).read_bytes())} byte(s) from {tmploc/f} to {self.install_location/f}')
                if to_replace:
                    logger.warning(f'Copying {len(to_replace)} file(s) as replacements')
                    for f in to_replace:
                        logger.terse(f'Replacing {self.install_location/f} with {tmploc/f}')
                        logger.trace(f'Copied {(self.install_location/f).write_bytes((tmploc/f).read_bytes())} byte(s) from {tmploc/f} to {self.install_location/f}')
        elif not to_remove:
            logger.warning('Nothing to do, upgrade cancelled')
            return
        if to_remove:
            logger.warning(f'Removing {len(to_remove)} file(s)')
            for f in to_remove:
                logger.warning(f'Unlinking {self.install_location/f}')
                (self.install_location/f).unlink()
            logger.info('Updating files database')
        self.files.clear()
        self.files.extend(sorted(to_install | to_replace))

    def sync(self, **update_kwargs):
        '''
            ...
            See `help(Package.update)` for `update_kwargs`
        '''
        logger.trace(f'Sync issued for: {self.blueprint.id}')
        self.config.save()
        self.update(**update_kwargs)
        self.upgrade()
        self.config.save()
    def add_draft(self, draft: str):
        '''
            Adds a draft to the configured drafts
            Does nothing if `draft` is already in the drafts list
            Drafts are installed on the next call to `sync()`/`upgrade()`
        '''
        if 'drafts' in self.config['drafts']: return
        if self.blueprint.drafts is None:
            raise TypeError(f'Cannot add draft {draft!r}, as the blueprint does not support drafts')
        if draft not in self.blueprint.drafts:
            raise ValueError(f'Cannot add draft {draft!r}, as it does not exist in the blueprint')
        self.config['drafts'].append(draft)
        with self._save_condition: self._save_condition.notify()
    def rm_draft(self, draft: str):
        '''
            Removes a draft from the configured drafts
            Does nothing if `draft` is not in the drafts list
            Drafts are removed on the next call to `sync()`/`upgrade()`
        '''
        try: self.config['drafts'].remove(draft)
        except ValueError: pass
