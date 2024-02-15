#!/bin/python3

'''
    Provides facilities for FlexiLynx's logging
    **WARNING**: importing this module has the side-affect of adding several new logging levels
'''

#> Imports
import typing
import logging
import logging.config
import logging.handlers
from configparser import RawConfigParser

from .tools.functools import mpartial
#</Imports

#> Header >/
__all__ = ('root_logger', 'core_logger', 'config')

# Set up loggers
root_logger = logging.getLogger('FL')
core_logger = root_logger.getChild('$core')
# Logging configuration functions
def config(d: dict):
    '''Configure Python's logging with a dict. You probably don't need to use this'''
    logging.config.dictConfig(d)
# Add new levels
logging.TRACE = (logging.DEBUG - logging.NOTSET) // 2
logging.VERBOSE = (logging.INFO - logging.DEBUG) // 2
logging.TERSE = (logging.WARNING - logging.INFO) // 2
logging.FATAL = logging.CRITICAL * 2
## Add level functions
lc = logging.getLoggerClass()
lc.trace = mpartial(lc.log, logging.TRACE)
lc.verbose = mpartial(lc.log, logging.VERBOSE)
lc.terse = mpartial(lc.log, logging.TERSE)
lc.fatal = mpartial(lc.log, logging.FATAL)
# Name levels
logging.addLevelName(logging.TRACE, 'TRC')
logging.addLevelName(logging.DEBUG, 'DBG')
logging.addLevelName(logging.VERBOSE, 'VRB')
logging.addLevelName(logging.INFO, 'INF')
logging.addLevelName(logging.TERSE, 'TRS')
logging.addLevelName(logging.WARNING, 'WRN')
logging.addLevelName(logging.ERROR, 'ERR')
logging.addLevelName(logging.CRITICAL, 'CRT')
logging.addLevelName(logging.FATAL, 'FTL')
# Level colors
class _ColoredLogger(logging.Formatter):
    COLORS = {k: '{}' if v is None else f'\x1b[{v}m{{}}\x1b[0m' for k,v in {
        logging.TRACE: '2;3', # faint, italic
        logging.DEBUG: '2', # faint
        logging.VERBOSE: None, # nothing
        logging.INFO: None, # nothing
        logging.TERSE: '3', # italic
        logging.WARNING: '33', # yellow fg
        logging.ERROR: '31', # red fg
        logging.CRITICAL: '1;31', # bold, red fg
        logging.FATAL: '1;5;31', # bold, blinking, red fg
    }.items()}
    def format(self, record: logging.LogRecord) -> str:
        return self.COLORS[record.levelno].format(super().format(record))
logging._ColoredLogger = _ColoredLogger
