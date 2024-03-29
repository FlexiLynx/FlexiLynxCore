#!/bin/python3

'''Utilities for flattening and unflattening data'''

#> Imports
import typing
import itertools
#</Imports

#> Header >/
__all__ = ('flatten_map', 'extrude_map',
           'iflatten_seq', 'flatten_seq')

# Maps
def flatten_map(m: typing.Mapping[str, typing.Any], delim: str | None = None) -> dict[tuple[str, ...] | str, typing.Any]:
    '''
        Flattens `m` into a dictionary with no depth
        If `delim` is not `None`, each key is joined together by it,
            otherwise each key is put in a tuple
    '''
    new = {}
    for k,v in m.items():
        if not isinstance(v, typing.Mapping):
            new[(k,)] = v
            continue
        for ik,iv in flatten_map(v).items():
            new[(k,)+ik] = iv
    if delim is not None:
        return {delim.join(k): v for k,v in new.items()}
    return new
def extrude_map(m: typing.Mapping[tuple[str, ...] | str, typing.Any], delim: str | None = None) -> dict[str, typing.Any]:
    '''Reverses the effects of `flatten_map()`'''
    new = {}
    for (l,k),_ in itertools.groupby(m.keys(), key=lambda k: ((len(k) if delim is None else k.count(delim)+1), k)):
        assert l
        ks = tuple(k if delim is None else k.split(delim))
        if l == 1:
            new[ks[0]] = m[k]
            continue
        if ks[0] not in new:
            new[ks[0]] = {}
        new[ks[0]][ks[1:]] = m[k]
    return {k: (extrude_map(v) if isinstance(v, dict) else v) for k,v in new.items()}
# Sequences
def iflatten_seq(s: typing.Sequence, type_: type = typing.Sequence) -> typing.Iterator:
    '''
        Flattens `s` into a sequence with no depth
        Sequences are checked (`isinstance()`) against `type_`
    '''
    for v in s:
        if isinstance(v, type_):
            yield from iflatten_seq(v)
        else: yield v
def flatten_seq(s: typing.Sequence, type_: type[typing.Sequence] = typing.Sequence, coerce: type = tuple) -> typing.Sequence | typing.Any:
    '''
        Flattens `s` into a sequence with no depth, using `iflatten_seq()`
        Sequences are checked (`isinstance()`) against `type_`
        The result is converted to `coerce`
    '''
    return coerce(iflatten_seq(s, type_))
