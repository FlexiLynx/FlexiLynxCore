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
__all__ = ('lambdas', 'reach', 'DEFAULT', 'defaults')

lambdas = types.SimpleNamespace(
    noop = lambda *args, **kwargs: None,
)

rlogger = logger.core_logger.getChild('reach')
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

class DEFAULT:
    def __new__(cls):
        return DEFAULT
    def __reduce__(self):
        return (type(self), ())
DEFAULT = object.__new__(DEFAULT)
def defaults(supplier: typing.Callable):
    '''
        Decorator to make a function automatically take default
            values from another
        Any default value of `DEFAULT` in the wrapped function is replaced with
            the corresponding default from `supplier`
        Note that this modifies the wrapped function in-place, it does not create a new one
    '''
    def mutator(target: typing.Callable) -> typing.Callable:
        if target.__defaults__ and supplier.__defaults__:
            target.__defaults__ = tuple((supplier.__defaults__[i] if d is DEFAULT else d) for i,d in enumerate(target.__defaults__))
        if target.__kwdefaults__ and supplier.__kwdefaults__:
            for k,v in target.__kwdefaults__.items():
                if v is not DEFAULT: continue
                target.__kwdefaults__[k] = supplier.__kwdefaults__[k]
        return target
    return mutator
