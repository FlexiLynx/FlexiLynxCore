#!/bin/python3

'''Supplies classes for packages'''

#> Imports
import typing
from pathlib import Path

from .blueprint import Blueprint
from .generate import hash_files

from . import logger

from FlexiLynx.core.util.functools import defaults, DEFAULT
#</Imports

#> Header >/
__all__ = ('BasePackage', 'FilesPackage', 'FilesystemPackage')

class BasePackage:
    '''
        Represents an abstract package that may or may not be on the system
        Mostly a container for a `Blueprint`
    '''
    __slots__ = ('blueprint',)

    def __init__(self, blueprint: Blueprint):
        self.blueprint = blueprint

    @defaults(Blueprint.update)
    def update(self, url: str | None = DEFAULT, *, fetchfn: typing.Callable[[str], bytes] = DEFAULT,
               verify: bool = DEFAULT, verify_self: bool = DEFAULT, key_update: Blueprint.KeyUpdate = DEFAULT):
        '''
            Updates this package's underlying blueprint
            See `help(Blueprint.update)` for information on arguments
        '''
        logger.debug('Issuing update to blueprint through package')
        logger.trace(f'{url=!r} {fetchfn=!r} {verify=!r} {verify_self=!r} {key_update=!r}')

class FilesPackage(BasePackage):
    '''Allows executing package-related file manipulation'''

    @defaults
    def scan(self, location: Path, draft: str | None = None):
        ...
class FilesystemPackage: pass
