#!/bin/python3

'''
    A collection of function and frame utilities,
        as well as some functions that are commonly created as lambdas
'''

#> Imports
import types
import inspect
from ..logger import core_logger
#</Imports

#> Header >/
__all__ = ('lambdas', 'reach')

lambdas = types.SimpleNamespace(
    noop = lambda *args, **kwargs: None,
)

rlogger = core_logger.getChild('reach')
def reach(n: int = 1, current: types.FrameType | None = None) -> types.FrameType:
    '''
        Reaches "up" `n` frames from `current`
        If `current` is `None`, the caller's frame is used instead
    '''
    if current is None:
        current = inspect.currentframe().f_back
    rlogger.trace(f'{current.f_globals["__name__"]!r} at {current.f_code.co_filename}@L{f.f_lineno}'
                  f' requesting to reach up {n} frames')
    for _ in range(n):
        current = current.f_back
    rlogger.trace(f'reached up {n} frames to {current.f_globals["__name__"]!r} at {current.f_code.co_filename}@L{f.f_lineno}')
    return current
