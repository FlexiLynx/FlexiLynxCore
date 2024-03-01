#!/bin/python3

'''Provides the `Plugin` class'''

#> Imports
import logging
from dataclasses import dataclass, field

from . import loader

from . import unbound_logger

from FlexiLynx.core.frameworks.module import Manager, Module
from FlexiLynx.core.frameworks.blueprint import Package
#</Imports

#> Header >/
__all__ = ('Plugin',)

@dataclass(slots=True, kw_only=True)
class Plugin:
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

    def __post_init__(self):
        self._bind_logger(self.bound.logger if isinstance(self.bound, Module)
                          else unbound_logger)

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
        self.loader.load(self)
    def setup(self):
        '''Sets up the plugin, delegating to `.loader.setup()`'''
        self.loader.setup(self)
