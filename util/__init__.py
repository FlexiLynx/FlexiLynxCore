#!/bin/python3

'''
    Utilities that are necessary for `FlexiLynxCore`
        and are exposed for convenience
'''

#> Package >/
__all__ = (
    # top-level
    'base85', 'pack', 'parallel', 'typing',
    # in folders
    ## tools
    'flattools', 'functools', 'moduletools', 'retools', 'seqtools'
    # singleton
    'Config', 'FlexiSpace',
)

# Top-level modules
from . import base85, pack, parallel, typing

# Modules in folders
from .tools import flattools, functools, moduletools, retools, seqtools

# Singleton modules
from .singleton.config import Config
from .singleton.flexispace import FlexiSpace
