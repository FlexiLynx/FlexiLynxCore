#!/bin/python3

'''Utilities for core FlexiLynx frameworks'''

#> Imports
import typing
from collections import abc as cabc
#</Imports

#> Header >/
__all__ = ('concat_mappings', 'dictdir', 'map_vals',
           'sequential')

# Mapping utilities
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
# Sequence utilities
def sequential(seq: typing.Iterable[int]) -> typing.Iterator[tuple[int, ...]]:
    '''Yields tuples of sequential integers in ascending order'''
    if not seq: return
    seq = sorted(seq)
    working = [seq[0]]
    if len(seq) < 2:
        yield tuple(working)
        return
    for n in seq[1:]:
        if n-1 != working[-1]:
            yield tuple(working)
            working = [n]
        else: working.append(n)
    yield tuple(working)
