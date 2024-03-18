#!/bin/python3

#> Imports
import operator
import itertools
import collections
from collections import abc as cabc
from functools import partial, partialmethod
#</Imports

#> Header >/
__all__ = ('orderedset', 'frozenorderedset')

class orderedset(cabc.MutableSet):
    __slots__ = ('__underlying',)

    def __init__(self, initial: cabc.Iterable = ()):
        self.__underlying = dict(zip(initial, itertools.repeat(None)))
    def __repr__(self) -> str:
        return f'{type(self).__name__}({{{", ".join(map(repr, self))}}})'
    # Methods for MutableSet
    def __contains__(self, item: cabc.Hashable) -> bool:
        return item in self.__underlying
    def __iter__(self) -> cabc.Iterable[cabc.Hashable]:
        return iter(self.__underlying)
    def __len__(self) -> int:
        return len(self.__underlying)
    def add(self, item: cabc.Hashable):
        self.__underlying[item] = None
    def discard(self, item: cabc.Hashable):
        self.__underlying.pop(item, None)
    # Indexing
    def index(self, item: cabc.Hashable):
        for i,e in enumerate(self):
            if e == item: return i
        raise ValueError(f'{item!r} is not in this orderedset')

class frozenorderedset(cabc.Set):
    def __new__(cls, initial: cabc.Iterable = ()):
        return dict.fromkeys(initial).keys()
frozenorderedset.register(collections.abc.KeysView)
