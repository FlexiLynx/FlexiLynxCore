#!/bin/python3

#> Imports
import inspect
import itertools
import collections
from collections import abc as cabc
from operator import attrgetter, methodcaller
from functools import partial, partialmethod
#</Imports

#> Header >/
__all__ = ('orderedset', 'frozenorderedset')

class orderedset(collections.OrderedDict, cabc.MutableSet):
    __slots__ = ('__dir',)

    def __new__(cls, initial: cabc.Iterable = ()):
        collections.OrderedDict.__new__(cls)
    def __init__(self, initial: cabc.Iterable = ()):
        super().__init__(zip(initial, itertools.repeat(None)))

    def add(self, elem: cabc.Hashable):
        super().__setitem__(elem, None)
    

    # Removed methods:
    __getitem__ = __setitem__ = __delitem__ = NotImplemented
    pop = popitem = NotImplemented
    keys = items = values = NotImplemented
    setdefault = NotImplemented
    fromkeys = NotImplemented
    def __dir__(self) -> tuple[str]:
        return self.__dir
    # Kept methods:
    #    __iter__, __reversed__, clear, copy
    # Modified methods:
    def update(self, *others: cabc.Set):
        for o in others: tuple(map(self.add, o))

    #unknown/todo: __ne__, __repr__, __reduce__, __eq__, __ior__, __or__, __ror__
    
orderedset._orderedset__dir = tuple(n for n,v in inspect.getmembers(orderedset) if v is not NotImplemented)

class frozenorderedset(cabc.Set):
    def __new__(cls, initial: cabc.Iterable = ()):
        return dict.fromkeys(initial).keys()
frozenorderedset.register(collections.abc.KeysView)
