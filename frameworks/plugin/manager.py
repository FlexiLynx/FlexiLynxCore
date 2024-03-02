#!/bin/python3

#> Imports
import typing
import operator
from pathlib import Path
from threading import RLock

from . import loader
from .plugin import Plugin

from . import logger

from FlexiLynx.core.frameworks import module
from FlexiLynx.core.util.parallel import mlock
#</Imports

#> Header >/
__all__ = ('Manager',)

class Manager:
    '''Serves as a database and manager of `Plugin`s'''
    __slots__ = ('bound', 'plugins', '_lock')

    def __init__(self, bound: module.Manager):
        self.bound = bound
        self.plugins = {}
        self._lock = RLock()

    @staticmethod
    def discover(path: Path) -> typing.Iterator[Path]:
        '''
            Discovers plugins in `path`
            Plugins are defined as folders containing a `plugin.json` file,
                so this will not find not-installed plugins that only contain a `blueprint.json`
        '''
        return map(operator.itemgetter(0), filter(lambda rdf: 'plugin.json' in rdf[2], path.walk()))

    @mlock
    def add_plugin(self, p: Plugin, *, override: bool = False):
        '''
            Adds a plugin to the manager, and binds it to the bound module manager
            Raises a `RuntimeError` if `p`'s ID is already registered, unless `override`
        '''
        prev = getattr(self.plugins, p.id, None)
        if not ((prev is None) or (prev is m)):
            msg = (f'Conflicting plugin IDs: {p.id}', f'Previous: {prev.package.at.as_posix()}\nNew: {m.package.at.as_posix()}')
            if not override:
                exc = RuntimeError(msg[0])
                exc.add_note(msg[1])
                raise exc
            logger.warning(f'{msg[0]}\n{msg[1]}')
        self.plugins[p.id] = p
        if p.bound is None: return
        logger.info(f'Binding {p.id}')
        p.bind(self.bound)
    @mlock
    def add_plugins(self, path: Path):
        '''Creates and adds all plugins from `path` using `.discover()`'''
        for p in self.discover(path):
            logger.verbose(f'Discovered plugin in {p}, attempting to add')
            self.add_plugin(loader.create_plugin(self.bound, p))

    def load_order(self) -> tuple[str, ...]:
        '''
            Generates a loading order from the plugins
            Currently only sorts by plugin ID, prioritizing on the dot right-to-left:
                'a.b.c' sorts after 'z.z.b',
                and 'a.b.c' sorts before 'a.c.c'
        '''
        return tuple(sorted(self.plugins.keys(), key=lambda pid: pid.split('.')[::-1]))

    def _plugin_foreach_at_state(self, func: str, target_state: Plugin.State, load_order: typing.Iterable[str] | None = None):
        if load_order is None: load_order = self.load_order()
        logger.info(f'Executing .{func}() on (up to) {len(load_order)} plugin(s)')
        logger.verbose(f'Target state: {target_state}')
        for p in load_order:
            if self.plugins[p].state is not target_state:
                logger.verbose(f'Skipping {p} in state {self.plugins[p].state}')
                continue
            logger.verbose(f'.{func}() on {p}')
            getattr(self.plugins[p], func)()
    def load_plugins(self, *, load_order: typing.Iterable[str] | None = None):
        '''
            Load plugins (that are in `Plugin.State.INIT`) in `load_order`
            If `load_order` is `None`, it is generated using `.load_order()`
        '''
        self._plugin_foreach_at_state('load', Plugin.State.INIT, load_order)
    def setup_plugins(self, *, load_order: typing.Iterable[str] | None = None):
        '''
            Setup plugins (that are in `Plugin.State.LOAD`) in `load_order`
            If `load_order` is `None`, it is generated using `.load_order()`
        '''
        self._plugin_foreach_at_state('setup', Plugin.State.LOAD, load_order)

