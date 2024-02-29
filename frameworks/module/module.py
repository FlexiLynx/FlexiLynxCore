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
        There are 3.5 `type`s of module:
          - "library": not meant to override anything, nor provide any functionality
                "functionality" also includes registering things
                In short, a "library" module does not interact with the program in any meaningful way by itself,
                    nor does it provide anything to an end-user
          - "override": meant to exclusively override functions or values that would normally also exist
          - "hybrid": the "3.5th" type of module; both provides new functions, and overrides
          - "implementation": meant to implement actual features
            The `type`s of modules are purely for documentation's sake in everything *except* loading order,
                which is biased in this order: "library", "hybrid", "override", "implementation"
    '''
    id: str = field(init=False)

    type: typing.Literal['library', 'override', 'hybrid', 'implementation']
    metadata: dict # populated by `module.json` for additional per-module configuration / data storage
    package: blueprint.Package

    entrypoint: types.ModuleType | None = field(init=False, default=None)
    logger: logging.Logger = field(init=False, default=None)

    def __post_init__(self):
        self.id = self.package.blueprint.id
        self.type = self.type.lower()
        if self.type not in {'library', 'override', 'hybrid', 'implementation'}:
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
