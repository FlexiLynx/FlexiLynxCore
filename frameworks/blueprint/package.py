#!/bin/python3

'''Supplies classes for packages'''

#> Imports
import json
import shutil
import typing
import operator
from pathlib import Path
from tempfile import TemporaryDirectory
from functools import cache

from .blueprint import Blueprint
from .generate import hash_files

from . import logger

from FlexiLynx.core.util import pack
from FlexiLynx.core.util import fstools
from FlexiLynx.core.util.net import fetchx
from FlexiLynx.core.util.hashtools import hash_many
from FlexiLynx.core.util.functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('Artifact', 'BasePackage', 'FilesPackage', 'FilesystemPackage', 'Package', 'TPackage')

class Artifact(typing.NamedTuple):
    hash: bytes
    hashfn: str
    url: str | None

class BasePackage:
    '''
        Represents an abstract package that may or may not be on the system
        Mostly a container for a `Blueprint`
    '''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

    def select(self, *drafts: str, include_main: bool = True) -> dict[str, Artifact]:
        '''
            Selects and returns `Artifact`s in each draft (and main, if `include_main`)
            All files in selected drafts override main files,
                and each subsequent draft overrides previous ones
        '''
        manifests = [self.blueprint.drafts[d] for d in drafts]
        if include_main: manifests.insert(0, self.blueprint.main)
        artifacts = {}
        for m in manifests:
            for f,h in m.files.items():
                if f in artifacts: continue
                artifacts[f] = Artifact(hash=h, hashfn=m.hash_method, url=None if m.url is None else f'{m.url}/{f}')
        return artifacts

    @defaults(Blueprint.update)
    def update(self, url: str | None = DEFAULT, *, fetchfn: typing.Callable[[str], bytes] = DEFAULT,
               verify: bool = DEFAULT, verify_self: bool = DEFAULT, key_update: Blueprint.KeyUpdate = DEFAULT):
        '''
            Updates this package's underlying blueprint
            See `help(Blueprint.update)` for information on arguments
        '''
        logger.debug('Issuing update to blueprint through package')
        logger.trace(f'{url=!r} {fetchfn=!r} {verify=!r} {verify_self=!r} {key_update=!r}')
        self.blueprint = self.blueprint.update(url, fetchfn=fetchfn, verify=verify, verify_self=verify_self, key_update=key_update)

class FilesPackage(BasePackage):
    '''Allows executing package-related file manipulation'''
    __slots__ = ()

    class ScanResult(typing.NamedTuple):
        matches: dict[str, Artifact]
        nomatch: dict[str, Artifact]
        missing: dict[str, Artifact]
    @defaults(hash_files)
    def scan(self, location: Path, *drafts: str, max_threads: int = DEFAULT) -> ScanResult:
        '''
            Returns a `ScanResult` of the files on the filesystem
            See `select()` for information on ordering of `drafts`
        '''
        logger.debug(f'Scanning location: {location}')
        logger.trace(f'{location=!r}, {drafts=!r}, {max_threads=!r}')
        files = self.select(*drafts)
        to_hash = {}
        missing = {}
        for fn,art in files.items():
            if (location/fn).exists():
                to_hash.setdefault(art.hashfn, {})
                to_hash[art.hashfn][fn] = art
            else: missing[fn] = art
        matches = {}; nomatch = {}
        for hfn,arts in to_hash.items():
            for f,h in hash_files(location, arts.keys(), max_threads=max_threads, hash_method=hfn).items():
                (matches if h == arts[f].hash else nomatch)[f] = arts[f]
        return self.ScanResult(matches=matches, nomatch=nomatch, missing=missing)

    @defaults(hash_many)
    def synchronize(self, location: Path, scan: ScanResult, *,
                    reject_mismatch: bool = True, max_threads: int = DEFAULT,
                    fetchfn: typing.Callable[[str, ...], tuple[bytes, ...]] = fetchx):
        '''
            Installs needed files (`nomatch` and `missing`) to `location` from a `ScanResult`
            If `reject_mismatch`, then downloaded data will also be checked against the blueprint,
                and a `ValueError` will be raised if any fail
            `max_threads` is the maximum amount of threads to use for hashing
        '''
        logger.terse(f'Synchronization issued: {self.blueprint.id}')
        if not (scan.nomatch or scan.missing):
            logger.terse('Synchronize issued, but no files need synchronization. Cancelling')
            return
        artifacts = scan.nomatch | scan.missing
        logger.info(f'{len(artifacts)} file(s) need to be downloaded')
        logger.verbose(f'{len(scan.nomatch)} outdated file(s) will be replaced, {len(scan.missing)} new file(s) will be installed, {len(scan.matches)} file(s) are up-to-date')
        urls = {k: a.url for k,a in artifacts.items()}
        if not all(urls.values()):
            logger.fatal('Some artifacts do not have URLs to update from, cannot continue!')
            logger.error(f'Artifacts:\n - {"\n - ".join(filter(lambda kv: not kv[1], urls.items()))}')
            raise TypeError('Some artifacts do not have URLs to update from')
        files = dict(zip(urls.keys(), fetchfn(*urls.values())))
        to_hash = {}
        for fn,cont in files.items():
            to_hash.setdefault(artifacts[fn].hashfn, {})
            to_hash[artifacts[fn].hashfn][fn] = cont
        hashes = {}
        for hfn,fs in to_hash.items():
            logger.trace(f'Hashing {sorted(fs.keys())} with {hfn!r}')
            hashes.update(zip(fs.keys(), hash_many(*fs.values(), hash_method=hfn)))
        ahashes = dict(zip(artifacts.keys(), map(operator.attrgetter('hash'), artifacts.values())))
        logger.trace(f'\nArtifact hashes:\n{ahashes}\nDownloaded hashes:\n{hashes}')
        if hashes != ahashes:
            mism = sorted(fn for fn,h in hashes.items() if h != ahashes[fn])
            logger.error('Artifact hashes do not match downloaded content')
            if reject_mismatch:
                exc = ValueError('Artifact hashes do not match downloaded content')
                exc.add_note(f'Mismatched files: {", ".join(mism)}')
                raise exc
            logger.warning('Continuing anyway--reject_mismatch is false')
            logger.info(f'Mismatching files:\n - {"\n - ".join(mism)}')
        for fn,fc in files.items():
            (location/fn).parent.mkdir(parents=True, exist_ok=True)
            logger.verbose(f'Wrote {(location/fn).write_bytes(fc)} byte(s) to {location/fn}')
    @defaults(synchronize)
    def safe_synchronize(self, location: Path, scan: ScanResult, *,
                         reject_mismatch: bool = DEFAULT, max_threads: int = DEFAULT,
                         fetchfn: typing.Callable[[str, ...], tuple[bytes, ...]] = DEFAULT):
        '''
            Executes `.synchronize()` in a temporary directory, then moves files over
            Helps prevent partial upgrades when `.synchronize()` fails
        '''
        with TemporaryDirectory(prefix='FlexiLynx.FilesPackage.safe_synchronize_') as tmpdir:
            tmpdir = Path(tmpdir)
            logger.info(f'Selected temporary directory: {tmpdir}; executing .synchronize()')
            self.synchronize(tmpdir, scan, reject_mismatch=reject_mismatch, max_threads=max_threads, fetchfn=fetchfn)
            for fn in scan.missing.keys():
                logger.verbose(f'Copying new file {fn}')
                (location/fn).parent.mkdir(exist_ok=True, parents=True)
                shutil.copy(tmpdir/fn, location/fn)
            for fn in scan.nomatch.keys():
                logger.verbose(f'Overwriting {fn}')
                (location/fn).parent.mkdir(exist_ok=True, parents=True)
                shutil.copy(tmpdir/fn, location/fn)

class FilesystemPackage(FilesPackage):
    '''
        Represent an actual package on the filesystem
        The path specified by `at` must, at the very least, exist and contain `blueprint.json`
    '''
    __slots__ = ('at', 'drafts', 'files')

    def __init__(self, at: Path):
        self.at = at
        super().__init__(Blueprint.deserialize((self.at/'blueprint.json').read_text()))
        if (self.at/'package_db.pakd').exists():
            self.drafts, self.files = map(set, pack.unpack((self.at/'package_db.pakd').read_bytes()))
        else:
            self.drafts = set()
            self.files = set()
        self.save()
    def save(self, to: Path | None = None):
        '''Saves all metadata to `to` (if given), or `.at`'''
        if to is None: to = self.at
        (to/'blueprint.json').write_text(self.blueprint.serialize())
        (to/'package_db.pakd').write_bytes(pack.pack(self.drafts, self.files))

    @defaults(FilesPackage.synchronize)
    def upgrade(self, *, use_safe_sync: bool = True, max_threads: int = DEFAULT,
                reject_mismatch: bool = DEFAULT, fetchfn: typing.Callable[[str, ...], tuple[bytes, ...]] = DEFAULT,
                clean_pycache: bool = True, clean_empty: bool = True, save_after: bool = True):
        '''
            Upgrades this package and the file database, automatically using `.scan()` and `.[safe_]synchronize()`
                Additionally removes tracked files that are no longer needed
            Uses `.synchronize()` instead of `.safe_synchronize()` if `use_safe_sync` is false
            `max_threads` is passed to both `.scan()` and `.[safe_]synchronize()`
            `clean_pycache` runs `FlexiLynx.core.util.fstools.clean_pycache()` on `.at` pre-upgrade
            `clean_empty` runs `FlexiLynx.core.util.fstools.clean_empty()` on `.at` post-upgrade
            `save_after` runs `.save()` after an upgrade
        '''
        if clean_pycache:
            logger.info('upgrade: cleaning pycache files')
            fstools.clean_pycache(self.at)
        logger.info('upgrade: executing scan()')
        sres = self.scan(self.at, *self.drafts, max_threads=max_threads)
        chfiles = frozenset(sres.nomatch.keys() | sres.missing.keys())
        rmfiles = self.files - sres.matches.keys() - chfiles
        if not (chfiles or rmfiles):
            logger.terse('upgrade: nothing to do')
            return
        if chfiles:
            logger.info(f'upgrade: executing {"safe_synchronize" if use_safe_sync else "synchronize"}()')
            (self.safe_synchronize if use_safe_sync else self.synchronize)(
                self.at, sres, reject_mismatch=reject_mismatch, max_threads=max_threads, fetchfn=fetchfn)
            logger.info('upgrade: synchronization complete')
        if rmfiles:
            logger.warning(f'upgrade: removing {len(rmfiles)} file(s)')
            for f in rmfiles:
                logger.verbose(f'upgrade: removing {f}')
                (self.at/f).unlink()
            logger.info('upgrade: removal complete')
        logger.info('upgrade: updating file database')
        self.files.clear()
        self.files.update(chfiles, sres.matches.keys())
        if clean_empty:
            logger.info('upgrade: cleaning empty directories')
            fstools.clean_empty(self.at)
        if save_after:
            logger.info('upgrade: automatically saving databases')
            self.save()

class Package:
    '''
        A generic wrapper around both `FilesPackage` and `FilesystemPackage`
        When initialized with a `Blueprint`, offers methods from `FilesPackage`
        When initialized with a `Path`, or after `.install()`, offers methods from `FilesystemPackage`
        Additionally offers a `.install()` method and `.installed` property

        This shouldn't be used for type checking if you want to also accept `FilesystemPackage` or `FilesPackage`,
            use `TPackage()` instead
    '''
    __slots__ = ('_package', '_installed')

    installed = property(operator.attrgetter('_installed'))

    def __init__(self, source: Blueprint | Path):
        if isinstance(source, Blueprint):
            self._installed = False
            self._package = FilesPackage(source)
        elif isinstance(source, Path):
            self._installed = True
            self._package = FilesystemPackage(source)
        else:
            raise TypeError('Cannot instantiate: "source" must be a Blueprint or Path, not {type(source)!r}')
    def __getattr__(self, attr: str) -> typing.Any:
        return getattr(self._package, attr)
    def __setattr__(self, attr: str, val: typing.Any):
        if attr.startswith('_'): super().__setattr__(attr, val)
        else: setattr(self._package, attr, val)
    def __dir__(self) -> list[str]:
        return super().__dir__() + dir(self._package)
    def __repr__(self) -> str:
        return f'<{type(self).__name__} {"[installed] " if self._installed else ""}{self._package!r}>'
    def install(self, to: Path):
        '''
            Converts this `Package` from "non-installed" mode to "installed" mode
            Note that this only creates a `blueprint.json` file in the target directory,
                and converts the underlying package to a `FilesystemPackage`
                `.upgrade()` should be used after this method to populate everything else
            This will fail if this `Package` is already in "installed" mode
        '''
        if self._installed:
            raise TypeError('This package is acting as a FilesystemPackage, and is already installed')
        (to/'blueprint.json').write_text(self._package.blueprint.serialize())
        self._package = FilesystemPackage(to)
        self._installed = True

class TPackage(type):
    '''
        Allows type checking/hinting for packages (probably only checkable during runtime, unless you have a very advanced static checker)
        If `installed` is true, then `FilesystemPackage` matches `isinstance` and `issubclass`,
            and `Package` instances where `.installed` is true match `isinstance`
        If `not_installed` is true, then `FilesPackage` matches `isinstance` and `issubclass`,
            and `Package` instances where `.installed` is false match `isinstance`
        `Package`s never match `issubclass`
    '''
    @cache
    def __new__(cls, *args, **kwargs) -> type:
        return super().__new__(cls, 'TPackage', (), {'__init__': NotImplemented})
    def __init__(self, installed: bool = True, not_installed: bool = False):
        self.installed = installed
        self.not_installed = not_installed

    def __hash__(self) -> int: return 0 # allows @cache

    def __subclasscheck__(cls, other: type) -> bool:
        return ((cls.installed and issubclass(other, FilesystemPackage))
                or (cls.not_installed and issubclass(other, FilesPackage)))
    def __instancecheck__(cls, other: object) -> bool:
        return (isinstance(other, Package) and ((cls.installed and other.installed)
                                                or (cls.not_installed and not other.installed))
                or (cls.installed and isinstance(other, FilesystemPackage))
                or (cls.not_installed and isinstance(other, FilesPackage)))
