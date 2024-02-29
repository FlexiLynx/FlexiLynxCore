#!/bin/python3

'''Supplies utilities for creating and loading `Module`s'''

#> Imports
import json
import typing
from types import ModuleType
from pathlib import Path

from .module import Module

from . import Consts

from FlexiLynx.core.util.moduletools import inject_import
from FlexiLynx.core.frameworks.blueprint import package
#</Imports

#> Header >/
__all__ = ('load_metadata', 'create_module', 'module_from_package', 'import_module')

def load_metadata(path: Path) -> dict:
    '''Loads module metadata from `path`'''
    return json.loads((path/'module.json').read_text())
def create_module(path: Path):
    '''Creates a `Module` from `path` using `module_from_package`'''
    return module_from_package(package.Package(path))
def module_from_package(pack: package.TPackage(installed=True, not_installed=False)):
    '''Creates a `Module` from a package'''
    meta = load_metadata(pack.at)
    return Module(type=meta['type'], metadata=meta, package=pack)
def import_module(mod: Module, extra_inject: dict[str, typing.Any] = {}) -> ModuleType:
    '''
        Given a `Module` (FlexiLynx module), import and return its **Python** module
        Note that this also injects `mod` as `Consts.THIS_NAME` ("this" by default)
            and `mod.logger` as `Consts.LOGGER_NAME` ("logger" by default)
            into the module's namespace before importing it, as well as any names in `extra_inject`
    '''
    return inject_import(mod.package.at/Consts.ENTRYPOINT_FILE, mod.id,
                         **({Consts.THIS_NAME: mod, Consts.LOGGER_NAME: mod.logger} | extra_inject))
