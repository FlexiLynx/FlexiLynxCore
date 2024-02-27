#!/bin/python3

'''
    Utilities that are necessary for `FlexiLynxCore`
        and are exposed for convenience
'''

#> Package >/
__all__ = (
    # top-level
    'base85', 'logger', 'net', 'pack', 'parallel', 'typing',
    # in folders
    ## tools
    'flattools', 'fstools', 'functools', 'hashtools', 'maptools', 'moduletools', 'retools', 'seqtools',
    ## singleton
    'Config', 'FlexiSpace',
)

# Top-level modules
from . import base85, logger, net, pack, parallel, typing

# Modules in folders
from .tools import flattools, fstools, functools, hashtools, maptools, moduletools, retools, seqtools

# Singleton modules
from .singleton.config import Config
from .singleton.flexispace import FlexiSpace
