#!/bin/python3

'''Utilities for core FlexiLynx frameworks'''

#> Imports
import typing
from collections import abc as cabc
#</Imports

#> Header >/
__all__ = ('concat_mappings', 'dictdir', 'map_vals')

def concat_mappings(*maps: typing.Mapping, type_: type[typing.Mapping] | typing.Callable[[tuple[tuple[typing.Any, typing.Any], ...]], typing.Any] = dict) -> typing.Mapping | typing.Any:
    '''Concatenates multiple mappings into a single one'''
    return type_(sum(map(tuple, map(cabc.ItemsView, maps)), start=()))
def dictdir(o: typing.Any) -> dict[str, typing.Any]:
    '''Gets an object's keys and values from its `__dict__` and `__slots__` attributes'''
    return {a: getattr(o, a) for a in getattr(o, '__slots__')} \
           | getattr(o, '__dict__', {})
def map_vals(func: typing.Callable[[typing.Any], typing.Any], *maps: typing.Mapping,
             type_: type[typing.Mapping] | typing.Callable[[tuple[tuple[typing.Any, typing.Any], ...]], typing.Any] = dict) -> typing.Mapping | typing.Any:
    '''Returns a dictionary composed of all of `maps`, where each value has been fed through `func`'''
    return concat_mappings(*({k: func(v) for k,v in m.items()} for m in maps), type_=type_)
