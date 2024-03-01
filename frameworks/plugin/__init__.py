#!/bin/python3

'''FlexiLynx's `plugin` framework'''

#> Imports
from FlexiLynx.core import logger
#</Imports

#> Package >/
__all__ = ('Plugin', 'logger', 'unbound_logger')

logger = logger.getChild('P')
unbound_logger = logger.getChild('@unbound')

from .plugin import Plugin
