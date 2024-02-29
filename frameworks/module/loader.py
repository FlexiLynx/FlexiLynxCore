#!/bin/python3

'''Supplies utilities for creating and loading `Module`s'''

#> Imports
import json
from pathlib import Path

from .module import Module

from FlexiLynx.core.util.moduletools import inject_import
from FlexiLynx.core.frameworks.blueprint import package
#</Imports

#> Header >/
__all__ = ('load_metadata', 'create_module', 'module_from_package')

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
