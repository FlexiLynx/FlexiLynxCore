#!/bin/python3

'''Provides the `Module` class'''

#> Imports
import typing
from dataclasses import dataclass, field

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
    main: str | None = None

    package: blueprint.Package

    def __post_init__(self):
        self.id = self.package.blueprint.id
        if self.type not in {'library', 'override', 'implementation'}:
            raise TypeError(f"Expected type to be one of 'library', 'override', or 'implementation', not {self.type!r}")
    def load(self):
        if not self.package.installed:
            raise TypeError('Cannot load this module when the underlying package is not installed')
    def exec(self):
        if not self.package.installed:
            raise TypeError('Cannot execute this module when the underlying package is not installed')
