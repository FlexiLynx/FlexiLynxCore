#!/bin/python3

'''
    A collection of function and frame utilities,
        as well as some functions that are commonly created as lambdas
'''

#> Imports
import types
import inspect
#</Imports

#> Header >/
__all__ = ('lambdas', 'reach')

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
    for _ in range(n):
        current = current.f_back
    return current
