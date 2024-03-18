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
    def index_dropwhile(self, item: cabc.Hashable) -> int:
        try:
            return next(
                itertools.dropwhile( # go through enumerate(self) until
                    lambda ii: (ii[1] != item), # the fetched item is equal to the target
                    enumerate(self)))[0] # return the index
        except StopIteration: # the item was never in the orderedset
            raise ValueError(f'{item!r} is not in this orderedset') from None
    def index_takewhile_for(self, item: cabc.Hashable) -> int:
        l = len(self)
        if not l: raise ValueError(f'{item!r} is not in this orderedset')
        i = -1
        for i,v in enumerate(itertools.takewhile(partial(operator.ne, item), self)): pass
        i += 1
        if i == l:
            raise ValueError(f'{item!r} is not in this orderedset')
        return i
    def index_takewhile_deque(self, item: cabc.Hashable) -> int:
        l = len(self)
        if not l: raise ValueError(f'{item!r} is not in this orderedset')
        d = collections.deque(maxlen=1)
        d.extend(enumerate(itertools.takewhile(partial(operator.ne, item), self)))
        if not d: return 0
        i = d[0][0] + 1
        if i == l:
            raise ValueError(f'{item!r} is not in this orderedset')
        return i
    def index_for(self, item: cabc.Hashable):
        for i,e in enumerate(self):
            if e == item: return i
        raise ValueError(f'{item!r} is not in this orderedset')
    def index_tuple(self, item: cabc.Hashable):
        try: return tuple(self).index(item)
        except ValueError: # the item was never in the orderedset
            raise ValueError(f'{item!r} is not in this orderedset') from None
    @staticmethod
    def _test_best_index(nruns=100000, sizes=(0, 10, 100, 1000, 10000),
                         methods=('index_dropwhile', 'index_takewhile_for', 'index_takewhile_deque', 'index_for', 'index_tuple')):
        import timeit
        print(f'Testing with all: {nruns=!r} {sizes=!r} {methods=!r}\nTimes are displayed in seconds')
        mlen = len(max(methods, key=len)) - 6 + 3
        for s in sizes:
            os = orderedset(range(s+1))
            print(f'{"-"*10}\nSize {s}:')
            print(f'{"Method:":^{mlen}} | {"Best case:":^19} | {"Avg. case:":^19} | {"Worst case:":^19} | {"Miss. case:":^19}')
            for m in methods:
                print(f'{f"""{m.removeprefix("index_")}():""":^{mlen}}', end='')
                for n in (0, s//2, s):
                    t = timeit.timeit(partial(getattr(os, m), n), number=nruns)
                    print(f' | {t/nruns:.3E}/{t:.3E}', end='')
                def _():
                    try: getattr(os, m)(n)
                    except ValueError: pass
                t = timeit.timeit(_, number=nruns)
                print(f' | {t/nruns:.3E}/{t:.3E}')
orderedset._test_best_index()

class frozenorderedset(cabc.Set):
    def __new__(cls, initial: cabc.Iterable = ()):
        return dict.fromkeys(initial).keys()
frozenorderedset.register(collections.abc.KeysView)
