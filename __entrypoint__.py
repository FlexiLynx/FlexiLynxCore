#!/bin/python3

#> Imports
import sys
import tomllib
from pathlib import Path
from importlib import import_module
#</Imports

#> Header
FlexiLynx = NotImplemented

MIN_PYTHON_VERSION = (3, 12, 0)

def _import(name):
    return import_module(f'.{name}' if __package__ else name, package=__package__)
#</Header

#> Main >/
def __load__():
    '''Load core Python modules'''
    # Check for minimum version
    assert sys.version_info[:3] >= MIN_PYTHON_VERSION, f'Minimum Python version not met! Need {".".join(map(str, MIN_PYTHON_VERSION))}, got {".".join(map(str, sys.version_info[:3]))}'
    # Import util
    util = _import('util')
    # Create FlexiLynx FlexiSpace
    global FlexiLynx
    FlexiLynx = util.FlexiSpace('FlexiLynx', 'The shared library across FlexiLynx')
    # Add utils
    (FlexiLynx@'core').util = util
def __setup__(log_cfg: Path = Path('logging.toml')):
    # Setup logger
    FlexiLynx.core.util.logger.init(tomllib.loads(log_cfg.read_text())
                                    if log_cfg.exists() else {})
    FlexiLynx.logger = FlexiLynx.core.util.logger.root_logger
    FlexiLynx.core.logger = FlexiLynx.core.util.logger.core_logger
    # Add frameworks
    FlexiLynx.core@'frameworks'
    FlexiLynx.core.frameworks.blueprint = _import('frameworks.blueprint')
    FlexiLynx.core.frameworks.module = _import('frameworks.module')
    FlexiLynx.core.frameworks.plugin = _import('frameworks.plugin')

if __name__ == '__main__':
    raise NotImplementedError('The __entrypoint__ should not be executed directly')
