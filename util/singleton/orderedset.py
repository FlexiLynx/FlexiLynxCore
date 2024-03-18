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
    def index_for(self, item: cabc.Hashable):
        for i,e in enumerate(self):
            if e == item: return i
        raise ValueError(f'{item!r} is not in this orderedset')
    def index_tuple(self, item: cabc.Hashable):
        try: return tuple(self).index(item)
        except ValueError: # the item was never in the orderedset
            raise ValueError(f'{item!r} is not in this orderedset') from None
    @staticmethod
    def _test_best_index(nruns=100000, sizes=(0, 10, 100, 1000, 10000)):
        import timeit
        timeit = partial(timeit.timeit, number=nruns)
        print(f'Testing {nruns} runs each\n[time per for]x[time per tuple] ([time total for]x[time total tuple])')
        for s in sizes:
            print(f'Size: {s}'.center(20, '-'))
            for cn,cv in {'Best': 0, 'Avg.': s//2, 'Wrst': s}.items():
                os = orderedset(range(s+1))
                print(f'{cn}-case: ', end='')
                tfort = timeit(partial(os.index_for, cv)); tfora = tfort/nruns
                ttupt = timeit(partial(os.index_tuple, cv)); ttupa = ttupt/nruns
                print(f'{tfora}{"<" if tfora < ttupa else ">" if tfora > ttupa else "-"}{ttupa} ({tfort}{"<" if tfort < ttupt else ">" if tfort > ttupt else "-"}{ttupt})')
orderedset._test_best_index()

class frozenorderedset(cabc.Set):
    def __new__(cls, initial: cabc.Iterable = ()):
        return dict.fromkeys(initial).keys()
frozenorderedset.register(collections.abc.KeysView)
