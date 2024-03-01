#!/bin/python3

#> Imports
import os
import sys
import logging, logging.config
from functools import partialmethod
#</Imports

#> Header >/
__all__ = ('root_logger', 'core_logger',
           'config', 'reconfigure')

root_logger = logging.getLogger('FL')
core_logger = root_logger.getChild('$core')

# Configuration
config = {
    'version': 1,
    'disable_existing_loggers': False,
    'names': {},
    'styling': {'do_style': False},
}
def reconfigure(conf: dict):
    '''(Re)configure the built-in logger and FlexiLynx's custom logging facilities'''
    # Update config dict
    for k,v in conf.items():
        if (k in config) and isinstance(v, dict): config[k] |= v
        else: config[k] = v
    # Add level names
    for oln,nln in config['names'].items():
        logging.addLevelName(logging.getLevelName(oln), nln)
    # Restyle formatter
    _StylishFormatter._restyle()
    # Configure basic logger
    logging.config.dictConfig(config)

# Stylish logging formatter
class _StylishFormatter(logging.Formatter):
    FORMAT_STYLE = '\x1b[{}m{{}}\x1b[0m'
    FORMAT_NO_STYLE = '{}'

    is_idle = getattr(sys.stderr, '__module__', '').startswith('idle')
    is_win = os.name == 'nt'

    _styles = {}
    _do_style = None

    @classmethod
    def _restyle(cls):
        cls._do_style = config['styling']['do_style'] \
                        and ((not cls.is_idle) or config['styling']['try_style_idle']) \
                        and ((not cls.is_win) or config['styling']['try_style_windows'])
        if not cls._do_style: return
        lnames = logging.getLevelNamesMapping()
        cls._styles = {lnames[ln]: cls.FORMAT_STYLE.format(s) if s else cls.FORMAT_NO_STYLE
                        for ln,s in config['styling']['levels'].items()}
    def format(self, record: logging.LogRecord) -> str:
        if not self._do_style: return super().format(record)
        return self._styles.get(record.levelno, self.FORMAT_NO_STYLE).format(super().format(record))

# Initialization
_initted = False
def _add_level(logcls: type, level_name: str, level_level: int):
    setattr(logging, level_name.upper(), level_level)
    logging.addLevelName(level_level, level_name.upper())
    setattr(logcls, level_name.lower(), partialmethod(logcls.log, level_level))
def init(conf: dict):
    '''Set up the logger, reading config from `conf`'''
    # Check if already initted
    global _initted
    if _initted:
        raise RuntimeError('Logging was already initialized! Maybe you meant `reconfigure()`?')
    _initted = True
    # Add levels
    logcls = logging.getLoggerClass()
    _add_level(logcls, 'trace', logging.NOTSET + ((logging.DEBUG - logging.NOTSET) // 2))
    _add_level(logcls, 'verbose', logging.DEBUG + ((logging.INFO - logging.DEBUG) // 2))
    _add_level(logcls, 'terse', logging.INFO + ((logging.WARNING - logging.INFO) // 2))
    _add_level(logcls, 'fatal', logging.CRITICAL * 2)
    # Set config
    reconfigure(conf)
