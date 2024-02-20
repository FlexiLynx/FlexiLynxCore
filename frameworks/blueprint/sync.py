#!/bin/python3

#> Imports
import typing

from .blueprint import Blueprint

from FlexiLynx.core.util import net
#</Imports

#> Header >/
__all__ = ('blueprint',)

def blueprint(b: Blueprint, url: str | None = None, *, fetchfn: typing.Callable[[str], bytes] = net.fetch1):
    '''
        Syncs a `Blueprint`, returning the newest version
        If `url` is not `None`, it is used in place of the `Blueprint`'s `url`
    '''
    if url is None: url = b.url
    if url is None:
        raise TypeError('No URL was provided and the blueprint has no URL')
    return Blueprint.deserialize(fetchfn(url).decode())
