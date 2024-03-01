#!/bin/python3

#> Imports
import sys
import typing
import tomllib
import logging
import importlib
from types import ModuleType
#</Imports

#> Header
MIN_PYTHON_VERSION = (3, 12, 0)
FlexiLynx = NotImplemented
def _resolve_import(modname: str, *, fn: typing.Callable = importlib.import_module):
    if not __package__:
        return fn(modname)
    return fn(f'.{modname}', package=__package__)
def __load__():
    '''Load core Python modules'''
    # Check for minimum version
    assert sys.version_info[:3] >= MIN_PYTHON_VERSION, f'Minimum Python version not met! Need {".".join(map(str, MIN_PYTHON_VERSION))}, got {".".join(map(str, sys.version_info[:3]))}'
    # Import util
    util = _resolve_import('util')
    # Create FlexiLynx FlexiSpace
    global FlexiLynx
    FlexiLynx = util.FlexiSpace('FlexiLynx', 'The shared library across FlexiLynx')
    # Add utils
    (FlexiLynx@'core').util = util
def __setup__():
    # Setup logger
    with open('logging.toml', 'rb') as f:
        FlexiLynx.core.util.logger.init(tomllib.load(f))
    FlexiLynx.logger = FlexiLynx.core.util.logger.root_logger
    FlexiLynx.core.logger = FlexiLynx.core.util.logger.core_logger
    # Add frameworks
    FlexiLynx.core@'frameworks'
    FlexiLynx.core.frameworks.blueprint = _resolve_import('frameworks.blueprint')
    FlexiLynx.core.frameworks.module = _resolve_import('frameworks.module')
    FlexiLynx.core.frameworks.plugins = _resolve_import('frameworks.plugin')
#</Header

#> Main >/
if __name__ == '__main__': raise NotImplementedError
