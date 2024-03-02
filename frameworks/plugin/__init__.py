#!/bin/python3

'''FlexiLynx's `plugin` framework'''

#> Imports
from FlexiLynx.core import logger
#</Imports

#> Package >/
__all__ = ('Plugin', 'Manager', 'loader', 'logger', 'unbound_logger')

logger = logger.getChild('P')
unbound_logger = logger.getChild('@unbound')

from . import loader
from .plugin import Plugin
from .manager import Manager
