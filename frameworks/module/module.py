#!/bin/python3

'''Provides the `Module` class'''

#> Imports
import types
import typing
import logging
from dataclasses import dataclass, field

from . import loader

from . import Consts

from FlexiLynx import logger
from FlexiLynx.core.frameworks import blueprint
#</Imports

#> Header >/
__all__ = ('Module',)

@dataclass(slots=True, kw_only=True)
class Module:
    '''
        A FlexiLynx module. Not to be confused with Python modules
        There are 3 `type`s of module:
          - "library": provides utility functions or classes to other modules and plugins
          - "override": overrides functions or values in either the built-in FlexiLynx code, or in other modules
          - "implementation": implement actual features; basically the "generic" module type
    '''
    id: str = field(init=False)

    type: typing.Literal['library', 'override', 'implementation']
    metadata: dict # populated by `module.json` for additional per-module configuration / data storage
    package: blueprint.Package

    entrypoint: types.ModuleType | None = field(init=False, default=None)
    logger: logging.Logger = field(init=False, default=None)

    def __post_init__(self):
        self.id = self.package.blueprint.id
        self.type = self.type.lower()
        if self.type not in {'library', 'override', 'implementation'}:
            raise TypeError(f"Expected type to be one of 'library', 'override', or 'implementation', not {self.type!r}")
        self.logger = logger.getChild(f'{self.type[0].upper()}#{self.id.replace(".", ":")}')
    def load(self):
        '''
            Loads the underlying *Python* module from the package into `.entrypoint`
            Additionally calls the initializer of the module, if present
                (`Consts.INIT_FUNC`, `__load__` by default)
        '''
        self.logger.info('load()')
        if not self.package.installed:
            raise TypeError('Cannot load this module when the underlying package is not installed')
        self.entrypoint = loader.import_module(self)
        if (ifn := getattr(self.entrypoint, Consts.INIT_FUNC, None)) is not None: ifn()
    def setup(self):
        '''Runs `.entrypoint`'s "setup" function (`Consts.SETUP_FUNC`, `__setup__` by default) if present'''
        self.logger.info('setup()')
        if self.entrypoint is None:
            raise TypeError('Cannot execute this module when the underlying entrypoint is not loaded')
        if (sfn := getattr(self.entrypoint, Consts.SETUP_FUNC, None)) is not None: sfn()
