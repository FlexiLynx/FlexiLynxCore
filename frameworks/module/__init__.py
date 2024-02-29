#!/bin/python3

'''FlexiLynx's `module` framework'''

#> Imports
from types import SimpleNamespace
from typing import Callable
#</Imports

#> Package >/
__all__ = ('Consts', 'Module', 'loader')

Consts = SimpleNamespace(
    ENTRYPOINT_FILE='__entrypoint__.py',
    THIS_NAME='this',
    INIT_FUNC='__load__',
    SETUP_FUNC='__setup__',
)

from . import loader # loading after `module` causes circular import
from .module import Module
