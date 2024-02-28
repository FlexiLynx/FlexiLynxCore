#!/bin/python3

'''Supplies classes for packages'''

#> Imports
import shutil
import typing
import operator
from pathlib import Path
from tempfile import TemporaryDirectory

from .blueprint import Blueprint
from .generate import hash_files

from . import logger

from FlexiLynx.core.util.net import fetchx
from FlexiLynx.core.util.hashtools import hash_many
from FlexiLynx.core.util.functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('Artifact', 'BasePackage', 'FilesPackage', 'FilesystemPackage')

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
            logger.error('Artifact hashes do not match downloaded content')
            if reject_mismatch: raise ValueError('Artifact hashes do not match downloaded content')
            logger.warning('Continuing anyway--reject_mismatch is false')
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
                shutil.copy(tmpdir/fn, location/fn)
            for fn in scan.nomatch.keys():
                logger.verbose(f'Overwriting {fn}')
                shutil.copy(tmpdir/fn, location/fn)

class FilesystemPackage:
    '''Represent an actual package on the filesystem'''
    __slots__ = ()
