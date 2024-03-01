#!/bin/python3

'''Provides the `BasePluginLoader` class and functions for loading plugins'''

#> Imports
import json
import typing
from abc import ABC, abstractmethod
from weakref import WeakValueDictionary
from pathlib import Path

from .plugin import Plugin

from . import logger

from FlexiLynx.core.frameworks.module import Manager
from FlexiLynx.core.frameworks.blueprint import package
#</Imports

#> Header >/
__all__ = ('BasePluginLoader', 'load_metadata', 'create_plugin', 'plugin_from_package', 'find_loader', 'loader_cache')

class BasePluginLoader(ABC):
    '''
        An abstract class for loading plugins
        Plugin loaders should be implemented as FlexiLynx modules
    '''
    __slots__ = ()

    def create(self, package: package.Package, plugin: dict) -> Plugin:
        '''Creates a new plugin from a `package` and a `plugin` metadata dictionary'''
        return Plugin(metadata=plugin, package=pack, bound=plugin.get('bound', None), loader=self)
    @abstractmethod
    def load(self, plugin: Plugin):
        '''Executed by `plugin.load()`'''
    @abstractmethod
    def setup(self, plugin: Plugin):
        '''Executed by `plugin.setup()`'''

def load_metadata(path: Path) -> dict:
    '''Loads plugin metadata from `path`'''
    return json.loads((path/'plugin.json').read_text())
def create_plugin(man: Manager, path: Path) -> Plugin:
    '''Creates a `Plugin` from `path`, sourcing its loader from modules in `man`'''
    return plugin_from_package(man, package.Package(path))
def plugin_from_package(man: Manager, pack: package.TPackage(installed=True, not_installed=False)) -> Plugin:
    '''Creates a `Plugin` from a package, sourcing its loader from modules in `man`'''
    meta = load_metadata(pack.at)
    return find_loader(man, meta['loader']).create(pack, meta)

loader_cache = {}
def find_loader(man: Manager, key: str, *, overwrite_cache: bool = False) -> BasePluginLoader:
    '''
        Finds the loader specified by `key` in `man`'s modules
        Raises `KeyError` if the module specified by `key` is not found
        Raises `ValueError` if the module does not have an `.entrypoint`
        Raises `AttributeError` if the module's `.entrypoint` does not have the
            attribute specified by `key`
        Raises `TypeError` if the attribute was found, but is not a subclass or instance of `BasePluginLoader`
        Note that the result is cached on a per-manager basis, and will be retrieved on subsequent requests unless
            `overwrite_cache` is true
            Note that the inner part of this cache, where loader instances are stored, uses weak references,
                so whenever all plugins related to a loader are lost, the loader itself should be lost as well
    '''
    cache = loader_cache.setdefault(id(man), WeakValueDictionary())
    if (not overwrite_cache) and ((loader := cache.get(key, None)) is not None): return loader
    modname,lname = key.split(':')
    logger.debug(f'Searching for loader {key!r} -- module {modname!r} / name {lname!r}')
    mod = man.modules.get(modname, None)
    if mod is None:
        raise KeyError(f'Cannot find loader {key!r} -- module {modname!r} not found')
    if mod.entrypoint is None:
        raise ValueError(f'Cannot find loader {key!r} -- module {modname!r} does not have an entrypoint')
    loader = getattr(mod.entrypoint, lname, None)
    if loader is None:
        raise AttributeError(f'Cannot find loader {key!r} -- module {modname!r} does not have the required attribute {lname!r}')
    logger.trace(loader)
    if isinstance(loader, type):
        if not issubclass(loader, BasePluginLoader):
            raise TypeError(f'Found loader {key!r} as type {loader!r}, but it is not a subclass of BasePluginLoader')
        loader = loader()
    elif not isinstance(loader, BasePluginLoader):
        raise TypeError(f'Found loader {key!r} as instance {loader!r}, but it is not an instance deriving from BasePluginLoader')
    cache[key] = loader
    return loader
