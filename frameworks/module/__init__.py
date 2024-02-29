#!/bin/python3

'''FlexiLynx's `module` framework'''

#> Imports
from types import SimpleNamespace
from typing import Callable

from FlexiLynx.core import logger
#</Imports

#> Package >/
__all__ = ('Consts', 'logger', 'Module', 'Manager', 'loader')

Consts = SimpleNamespace(
    ENTRYPOINT_FILE='__entrypoint__.py',
    THIS_NAME='this', LOGGER_NAME='logger',
    INIT_FUNC='__load__', SETUP_FUNC='__setup__',
)
logger = logger.getChild('M')

from . import loader # loading after `module` causes a circular import
from .module import Module
from .manager import Manager
