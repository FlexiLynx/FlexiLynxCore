#!/bin/python3

'''Supplies classes for packages'''

#> Imports
import typing
import operator
from pathlib import Path

from .blueprint import Blueprint
from .generate import hash_files

from . import logger

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

    class ScanResult(typing.NamedTuple):
        matches: frozenset[Artifact]
        nomatch: frozenset[Artifact]
        missing: frozenset[Artifact]
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
        missing = set()
        for fn,art in files.items():
            if (location/fn).exists():
                to_hash.setdefault(art.hashfn, {})
                to_hash[art.hashfn][fn] = art
            else: missing.add(art)
        matches = set(); nomatch = set()
        for hfn,arts in to_hash.items():
            for f,h in hash_files(location, arts.keys(), max_threads=max_threads, hash_method=hfn).items():
                (matches if h == arts[f].hash else nomatch).add(f)
        return self.ScanResult(matches=frozenset(matches), nomatch=frozenset(nomatch), missing=frozenset(missing))
    def synchronize(self, location: Path, scan: ScanResult):
        '''Installs needed files (`nomatch` and `missing`) to a location from a `ScanResult`'''

class FilesystemPackage: pass
