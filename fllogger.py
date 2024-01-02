#!/bin/python3

'''
    Provides a framework for FlexiLynx's logging, as well as possibly useful facilities for coloring terminal output

    The builtin logging facilities can be configured through the `FLLOGCFG` environment variable, or `FLLOGCFG.flynx.env` file as such:
      - TO BE ADDED

    As for the module API, note that whilst not mentioned in `__all__` (due to the very small possibility of external use), the following symbols are considered fully public:
      - `colorfmt_from_str()`
      - `class ColoredFormatter`
      - `mklogger()`
      - `VERBOSITY_LEVELS`
      - `VERBOSITY_OFFSET`
'''

#> Imports
import gzip
import logging, logging.handlers
import typing
from pathlib import Path
from enum import StrEnum
from functools import partialmethod

try:
    from colorama import init as colorama_init
except ModuleNotFoundError: colorama_init = None

from FlexiLynx.core.envconfiglib import EnvConfig
#</Imports

# Ensure _colorama_initted survives through importlib.reload
if '_colorama_initted' not in globals():
    _colorama_initted = False

#> Header >/
__all__ = ('LoggerConfig', 'FGColors', 'FGBColors', 'BGColors', 'BGBColors')

LoggerConfig = EnvConfig('FLLOGCFG', str)

# Setup colors
CODE_FMT = '\x1b[{}m'
class _ColorBase(StrEnum):
    __slots__ = ()
    def render(self, s: str) -> str: return f'{self.value}{s}{self._RESET.value}'
_raw_colors = {'BLACK': 30, 'RED': 31, 'GREEN': 32, 'YELLOW': 33, 'BLUE': 34, 'MAGENTA': 35, 'CYAN': 36, 'WHITE': 37, '_RESET': 39}
FGColors = _ColorBase('FGColors', {k: CODE_FMT.format(v) for k,v in _raw_colors.items()})
FGBColors = _ColorBase('FGBColors', {k: CODE_FMT.format(v+60) for k,v in _raw_colors.items()} | {'_RESET': FGColors['_RESET']})
BGColors = _ColorBase('BGColors', {k: CODE_FMT.format(v+10) for k,v in _raw_colors.items()})
BGBColors = _ColorBase('BGBColors', {k: CODE_FMT.format(v+70) for k,v in _raw_colors.items()} | {'_RESET': BGColors['_RESET']})
def colorfmt_from_str(color: str) -> str:
    '''
        Handles colors from a structured string, returning a string to be used with `str.format()`

        Explanation of syntax:
            `FG:{color}` - a simple foreground color (`{color}` also resolves to this)
                `FGB:{color}` - a "brightened" version of the same foreground color
            `BG:{color}` - a simple background color
                `BGB:{color}` - a "brightened" version of the same background color
            `FG[B]:{color1}+BG[B]:{color2}` - a ["brightened"] foreground (`color1`) and ["brightened"] background (`color2`) color
        Examples of syntax:
            `FG:BLACK+BG:WHITE` - simple black text on white background
                `BLACK+BG:WHITE` - same as above
            `FGB:YELLOW` - "brightened" yellow text on default background
            `BG:BLACK` - default text on black background
            `` - default text on default background
    '''
    cpmap = {'FG': FGColors, 'FGB': FGBColors,
             'BG': BGColors, 'BGB': BGBColors}
    s = '{}'
    for c in color.upper().split('+'):
        if ':' not in c:
            assert c != '_RESET'
            s = FGColors[c].render(s)
            continue
        t,n = c.split(':')
        assert n != '_RESET'
        assert t in cpmap, f'Color-prefix {t!r} is meaningless (part of {c!r})'
        s = cpmap[t][n].render(s)
    return s
# Colored formatter
class ColoredFormatter(logging.Formatter):
    '''
        A logging formatter to add colors to each logging level, using the syntax of `colorfmt_from_str()`

        These colors are configured using the `FLLOGCFG` environment variable or `FLLOGCFG.flynx.env` file as such:
          - To set INFO log-level to have a black foreground and IRRC (irrecoverable) to have a red background:
            `FLLOGCFG="color.info='fg:black' color.irrc='bg:red'"`
          - To set VERB (verbose) log-level to have a "brightened" green foreground and a black background:
            `FLLOGCFG="color.verb='fgb:green+bg:black'"`
        Note that log levels are not case-sensitive
        Each of the log levels' keys are as they appear in the outputted header, namely:
          - `????` for "not set" or "unknown" levels
          - `DEBG` for debug messages
          - `VERB` for verbose messages
          - `INFO` for info ("base-level") messages
          - `WARN` for warnings
          - `ERRO` for errors
          - `CRIT` for critical errors
          - `IRRC` for irrecoverable failures
    '''

    __slots__ = ('_level_to_color',)
    _default_colors = {
        '????': 'FG:WHITE',
        'DEBG': 'FG:GREEN',
        'VERB': 'FGB:GREEN',
        'INFO': 'FGB:WHITE',
        'WARN': 'FGB:YELLOW',
        'ERRO': 'FGB:RED',
        'CRIT': 'FG:RED',
        'IRRC': 'FG:WHITE+BG:RED',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._level_to_color = {k: colorfmt_from_str(LoggerConfig.get(f'color.{k.lower()}', v)) for k,v in self._default_colors.items()}
    def format(self, record: logging.LogRecord) -> str:
        record.msg = self._level_to_color[record.levelname].format(record.msg)
        return super().format(record)
# Logging setup
def setup(no_color: bool):
    # Create new levels
    logging.VERBOSE = (logging.DEBUG + logging.INFO) // 2
    logging.IRRECOVERABLE = logging.CRITICAL * 2
    ## Add logging methods
    lc = logging.getLoggerClass()
    lc.verbose = partialmethod(lc.log, logging.VERBOSE)
    lc.irrec = partialmethod(lc.log, logging.IRRECOVERABLE)
    # Set level names
    logging.addLevelName(logging.NOTSET,        '????')
    logging.addLevelName(logging.DEBUG,         'DEBG')
    logging.addLevelName(logging.VERBOSE,       'VERB')
    logging.addLevelName(logging.INFO,          'INFO')
    logging.addLevelName(logging.WARNING,       'WARN')
    logging.addLevelName(logging.ERROR,         'ERRO')
    logging.addLevelName(logging.CRITICAL,      'CRIT')
    logging.addLevelName(logging.IRRECOVERABLE, 'IRRC')
    # Run colorama init if possible
    if no_color: return
    global _colorama_initted
    if not _colorama_initted:
        _colorama_initted = True
        if colorama_init is None:
            print('Warning: colorama is not installed, so colors may not be available\nTo disable this message, add "no_colorama=1" to FLLOGCFG\n or to disable colors and this message, add "no_color=1"', file=sys.stderr)
            return
        colorama_init()
# Handler makers
VERBOSITY_LEVELS = (
    'IRRC', # -4
    'CRIT', # -3
    'ERRO', # -2
    'WARN', # -1
    'INFO', #  0
    'VERB', #  1
    'DEBG', #  2
    '????', #  3
)
VERBOSITY_OFFSET = 4
def mk_stream_h(verbosity: int | str, fmt: logging.Formatter) -> logging.StreamHandler:
    # Setup handler and formatting
    stream_h = logging.StreamHandler()
    stream_h.setFormatter(fmt)
    # Set verbosity
    if isinstance(verbosity, int):
        assert -4 <= verbosity <= 3, 'Verbosity index out of range (must be >= -4, <= 3)'
        verbosity = VERBOSITY_LEVELS[verbosity+VERBOSITY_OFFSET]
    stream_h.setLevel(logging.getLevelNamesMapping()[verbosity])
    return stream_h
def mk_mainfile_h(path: Path, fmt: logging.Formatter) -> logging.handlers.RotatingFileHandler:
    path.mkdir(exist_ok=True, parents=True)
    mainfile_h = logging.handlers.RotatingFileHandler(path / 'FlexiLynx.log',
                                                      maxBytes=1024**2 * float(LoggerConfig.get('file_size_mb', '0.1')),
                                                      backupCount=int(LoggerConfig.get('file_backups', '12')))
    mainfile_h.setFormatter(fmt)
    mainfile_h.setLevel(logging.INFO)
    def mainfile_h_rotator(src: str, dst: str):
        with open(src, 'rb') as srcd, gzip.open(dst, 'wb') as dstd:
            dstd.write(srcd.read())
        Path(src).unlink()
    mainfile_h.rotator = mainfile_h_rotator
    mainfile_h.namer = lambda n: f'{n}.log.gz'
    return mainfile_h
def mk_debugfile_h(path: Path, fmt: logging.Formatter) -> logging.handlers.RotatingFileHandler:
    path.mkdir(exist_ok=True, parents=True)
    (path / 'FlexiLynx.debug.log').unlink(missing_ok=True)
    debugfile_h = logging.handlers.RotatingFileHandler(path / 'FlexiLynx.debug.log', mode='w', backupCount=1,
                                                       maxBytes=1024**2 * float(LoggerConfig.get('debug_file_size_mb', '4')))
    debugfile_h.setFormatter(fmt)
    debugfile_h.setLevel(logging.DEBUG)
    debugfile_h.rotator = lambda src,dst: Path(src).unlink()
    return debugfile_h
# Logger maker
def mklogger() -> logging.Logger:
    no_color = LoggerConfig.get_bool('no_color')
    # Setup logging and colors
    setup(no_color or LoggerConfig.get_bool('no_colorama'))
    # Get verbosity
    if (verbosity := LoggerConfig.get('verbosity', '0')) \
            not in logging.getLevelNamesMapping():
        verbosity = int(verbosity)
    # Create logger
    logger = logging.getLogger('FL')
    logger.setLevel(logging.DEBUG)
    logger.propogate = False
    # Create formatters
    stream_fmt = (logging.Formatter if no_color else ColoredFormatter)(
        LoggerConfig.get('header_format', '[{asctime}] [{name}/{levelname}]: {message}'),
        LoggerConfig.get('date_format', '%H:%M:%S'), style='{')
    file_fmt = logging.Formatter(
        LoggerConfig.get('file_header_format', '[{asctime}] [{name}/{processName}:{threadName}<{module}.{funcName}[{lineno}]>/{levelname}]: {message}'),
        LoggerConfig.get('%Y-%m-%d %H:%M:%S'), style='{')
    # Create handlers
    ## File handlers
    p = Path(LoggerConfig.get('file_log_path', './FlexiLynx_logs/'))
    ### Main file handler
    if LoggerConfig.get('log_to_file', '1'):
        logger.addHandler(mk_mainfile_h(p, file_fmt))
    ### Debug file handler
    if LoggerConfig.get('debug_to_file', '1'):
        logger.addHandler(mk_debugfile_h(p, file_fmt))
    ## STDERR stream handler
    logger.addHandler(mk_stream_h(verbosity, stream_fmt))
    # Finish up
    return logger
