#!/bin/python3

'''
    Parts of manifests

    Each part contains data, a name, and various helper methods
    Different types of manifests may use different parts
'''

#> Imports
from functools import partial
from dataclasses import field

from .parts_base import *
from . import parts_base as base # re-exposed as base
#</Imports

#> Header >/
# Setup __all__
__all__ = ['base',]
_make_part = partial(make_struct_part, add_to_all=__all__)

# Parts classes
@_make_part('!id') # use special characters to delimit most important parts
class IDManifestPart:
    id:   str = field(kw_only=False)
    rel:  int = field(kw_only=False)
    type: str | None = None

# Finalize __all__
__all__ = tuple(__all__)
