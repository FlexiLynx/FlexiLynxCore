#!/bin/python3

'''Iterator/sequence utilities not found in the built-in utilities'''

#> Imports
import typing
import numbers
import operator
from collections import deque
#</Imports

#> Header >/
__all__ = ('sequential',)

def sequential(seq: typing.Iterable[numbers.Real], gap: numbers.Real = 1,
               gop: typing.Callable[[numbers.Real, numbers.Real], numbers.Real] = operator.sub,
               cop: typing.Callable[[numbers.Real, numbers.Real], bool | typing.Any] = operator.ne,
               sop: typing.Callable[[numbers.Real, numbers.Real], bool | typing.Any] = operator.eq,
               sortfn: typing.Callable[[typing.Iterable[numbers.Real]], typing.Sequence[numbers.Real]] = sorted) -> typing.Iterator[tuple[numbers.Real, ...]]:
    '''
        Yields tuples of sequential numbers
            The sequence is sorted using `sortfn`
        Operators:
            Examples are listed below each operation, with `n` corresponding to the current number and `p` corresponding to the previous
          - `gop()` stands for gap-op and is the operation to use with the current number and `gap` (by default, `operator.sub()`, or `-`)
                `gop(n, gap)` is what to compare with `p`, and defaults to `n-gap`
          - `cop()` stands for compare-op and is the operation to use to compare if `gop()` of the current number and `gap` are *different* from the previous number (by default, `operator.ne()`, or `!=`)
                `cop(gop(n, gap), p)` will return true if the sequence breaks here and a new sequence is started, and defaults to `(n-gap) != p`
          - `sop()` stands for same-op and is the operation to use to compare if the current number is the same as the previous number (by default, `operator.eq()`, or `==`)
                `sop(n, p)` will return true if the sequence duplicates `n`, so `n` is not different from `p`
    '''
    seq = sortfn(seq)
    if not seq: return
    working = deque((seq[0],))
    for n in seq[1:]:
        if ((not sop(n, working[-1])) and # (n == working[-1]) by default
                cop(gop(n, gap), working[-1])): # (n-1) != working[-1] by default
            yield tuple(working)
            working.clear()
        working.append(n)
    if working: yield tuple(working)
