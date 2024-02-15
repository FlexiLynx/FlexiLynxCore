#!/bin/python3

'''
    A collection of function and frame utilities,
        as well as some functions that are commonly created as lambdas
'''

#> Imports
import types
import typing
import inspect
import functools
from .. import logger
#</Imports

#> Header >/
__all__ = ('lambdas', 'reach', 'fpartial', 'mpartial')

lambdas = types.SimpleNamespace(
    noop = lambda *args, **kwargs: None,
)

def reach(n: int = 1, current: types.FrameType | None = None) -> types.FrameType:
    '''
        Reaches "up" `n` frames from `current`
        If `current` is `None`, the caller's frame is used instead
    '''
    if current is None:
        current = inspect.currentframe().f_back
    rlogger = logger.core_logger.getChild('reach')
    rlogger.trace(f'{current.f_globals["__name__"]!r} at {current.f_code.co_filename}@L{f.f_lineno}'
                  f' requesting to reach up {n} frames')
    for _ in range(n):
        current = current.f_back
    rlogger.trace(f'reached up {n} frames to {current.f_globals["__name__"]!r} at {current.f_code.co_filename}@L{f.f_lineno}')
    return current

def fpartial(f: typing.Callable, *args, **kwargs) -> types.FunctionType:
    '''Similar to `functools.partial()`, but returns an actual `types.FunctionType` object'''
    @functools.wraps(f)
    def partialed(*iargs, **ikwargs) -> typing.Any:
        return f(*args, *iargs, **kwargs, **ikwargs)
    return partialed
def mpartial(f: typing.Callable[[object, ...], ...], *args, **kwargs) -> types.FunctionType:
    '''Similar to `fpartial()`, but supports being used as methods and classmethods'''
    @functools.wraps(f)
    def partialed(self_or_cls, *iargs, **ikwargs) -> typing.Any:
        print(self_or_cls)
        print(args, iargs)
        print(kwargs, ikwargs)
        return f(self_or_cls, *args, *iargs, **kwargs, **ikwargs)
    return partialed
