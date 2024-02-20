#!/bin/python3

'''
    Provides facilities for FlexiLynx's logging
    **WARNING**: importing this module has the side-effect of adding several new logging levels, among other things
'''

#> Imports
import sys
import typing
import logging
import logging.config
import logging.handlers
from functools import partialmethod
from configparser import RawConfigParser
#</Imports

#> Header >/
__all__ = ('root_logger', 'core_logger', 'config', 'fl_logging_conf')

# Check if running under IDLE
# Set up loggers
root_logger = logging.getLogger('FL')
core_logger = root_logger.getChild('$core')
# Logging configuration functions
fl_logging_conf = {'styles': {}}
def config(d: dict):
    '''Configure FlexiLynx's logging with a dict. You probably don't need to use this'''
    global fl_logging_conf
    if 'flexilynx' in d:
        for k,v in d['flexilynx'].items():
            if hasattr(fl_logging_conf, k) and isinstance(v, dict):
                fl_logging_conf[k] |= v
            else:
                fl_logging_conf[k] = v.encode().decode('unicode_escape') if isinstance(v, str) else v
    logging.config.dictConfig(d)
    _StylishLogger._do_style = fl_logging_conf.get('do_style', True) and not (
        fl_logging_conf.get('detect_idle_no_style', True)
        and getattr(sys.stdin, '__module__', '').startswith('idlelib'))
    if _StylishLogger._do_style:
        _StylishLogger.gen_styles()
    print(fl_logging_conf)
# Add new levels
logging.TRACE = logging.NOTSET + ((logging.DEBUG - logging.NOTSET) // 2)
logging.addLevelName(logging.TRACE, 'TRACE')
logging.VERBOSE = logging.DEBUG + ((logging.INFO - logging.DEBUG) // 2)
logging.addLevelName(logging.VERBOSE, 'VERBOSE')
logging.TERSE = logging.INFO + ((logging.WARNING - logging.INFO) // 2)
logging.addLevelName(logging.TERSE, 'TERSE')
logging.FATAL = logging.CRITICAL * 2
logging.addLevelName(logging.FATAL, 'FATAL')
## Add level functions
lc = logging.getLoggerClass()
lc.trace = partialmethod(lc.log, logging.TRACE)
lc.verbose = partialmethod(lc.log, logging.VERBOSE)
lc.terse = partialmethod(lc.log, logging.TERSE)
lc.fatal = partialmethod(lc.log, logging.FATAL)
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
# Level styling
class _StylishLogger(logging.Formatter):
    _do_style = True
    styles = None
    @classmethod
    def gen_styles(cls):
        cls.styles = {k: fl_logging_conf.get('no_style_fmt', '{}') if v in {None, False} else fl_logging_conf.get('control_fmt', '\x1b[{v}m{{}}\x1b[0m').format(v=v) for k,v in {
            logging.TRACE: fl_logging_conf['styles'].get('TRACE', '2;3'), # faint, italic
            logging.DEBUG: fl_logging_conf['styles'].get('DEBUG', '2'), # faint
            logging.VERBOSE: fl_logging_conf['styles'].get('VERBOSE', None), # nothing
            logging.INFO: fl_logging_conf['styles'].get('INFO', None), # nothing
            logging.TERSE: fl_logging_conf['styles'].get('TERSE', '3'), # italic
            logging.WARNING: fl_logging_conf['styles'].get('WARNING', '33'), # yellow fg
            logging.ERROR: fl_logging_conf['styles'].get('ERROR', '31'), # red fg
            logging.CRITICAL: fl_logging_conf['styles'].get('CRITICAL', '1;31'), # bold, red fg
            logging.FATAL: fl_logging_conf['styles'].get('FATAL', '1;5;31'), # bold, blinking, red fg
        }.items()}
    def format(self, record: logging.LogRecord) -> str:
        if not self._do_style: return super().format(record)
        return self.styles[record.levelno].format(super().format(record))
_StylishLogger.gen_styles()
logging._StylishLogger = _StylishLogger
