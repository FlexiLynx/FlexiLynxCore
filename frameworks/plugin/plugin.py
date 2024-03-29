#!/bin/python3

'''Provides the `Plugin` class'''

#> Imports
import logging
import operator
from enum import Enum
from dataclasses import dataclass, field

from . import loader

from . import unbound_logger

from FlexiLynx.core.frameworks.module import Manager, Module
from FlexiLynx.core.frameworks.blueprint import Package
#</Imports

#> Header >/
__all__ = ('Plugin',)

class _LetThereBeDict: __slots__ = ('__dict__',)

@dataclass(slots=True, kw_only=True)
class Plugin(_LetThereBeDict):
    '''
        A FlexiLynx plugin
        Could be bound to a module, depending on the value of `.bound`:
          - A `Module` means that it is bound
          - A `str` means that it in unbound, but bindable
          - A `None` means that it is unbindable
    '''

    id: str = field(init=False)

    metadata: dict # populated by `plugin.json` for additional per-plugin configuration / data storage
    package: Package

    logger: logging.Logger = field(init=False, default=None)

    bound: Module | str | None

    loader: 'loader.BasePluginLoader'

    State = Enum('State', ('NONE', 'INIT', 'LOAD', 'SETUP'))
    _state: State = field(init=False, default=State.NONE)
    state = property(operator.attrgetter('_state'))

    def __post_init__(self):
        self.id = self.package.blueprint.id
        self._bind_logger(self.bound.logger if isinstance(self.bound, Module)
                          else unbound_logger)
        self._state = self.State.INIT

    def _bind_logger(self, logger: logging.Logger):
        self.logger = logger.getChild(f'@{self.id}')
    def bind(self, m: Manager):
        '''Binds this `Plugin` to its respective `Module` in `m`'''
        if self.bound is None:
            raise TypeError('Cannot bind an unbindable plugin (bound=None)')
        if isinstance(self.bound, Module):
            raise TypeError('Cannot bind an already bound plugin')
        if self.bound not in m.modules:
            raise KeyError(f'Cannot bind to module {self.bound!r}, as it is not registered')
        self.bound = m.modules[bound]
        self._bind_logger(self.bound.logger)

    def load(self):
        '''Loads the plugin, delegating to `.loader.load()`'''
        if self.state is not self.State.INIT:
            raise TypeError(f'Cannot load this plugin when not in State.INIT (currently in {self.state})')
        self.loader.load(self)
        self._state = self.State.LOAD
    def setup(self):
        '''Sets up the plugin, delegating to `.loader.setup()`'''
        if self.state is not self.State.LOAD:
            raise TypeError(f'Cannot load this plugin when not in State.LOAD (currently in {self.state})')
        self.loader.setup(self)
        self._state = self.State.SETUP
