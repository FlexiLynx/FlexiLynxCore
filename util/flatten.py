#!/bin/python3

'''Utilities for flattening and unflattening data'''

#> Imports
import typing
#</Imports

#> Header >/
__all__ = ('flatten_map',)

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
