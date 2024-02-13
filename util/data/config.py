#!/bin/python3

'''
    Provides very basic JSON-based configuration for FlexiLynx, in a not-super-readable format
        It is recommended to suggest that end-users install a module that provides configuration options
'''

#> Imports
import json
import typing
from pathlib import Path
from threading import RLock
from collections import UserDict

from ..parallel import mlock
#</Imports

#> Header >/
__all__ = ('Config',)

class Config(UserDict):
    __slots__ = ('data', 'path', 'defaults', '_lock')

    def __init__(self, path: Path):
        self.data = {}
        self.path = path
        path.parent.mkdir(exist_ok=True, parents=True)
        self.defaults = set()
        self._lock = RLock()

    @mlock
    def __setitem__(self, item: str, val: typing.Any):
        if item in self.defaults:
            self.defaults.remove(item)
        self.data[item] = val
    @mlock
    def __delitem__(self, item: str):
        if item in self.defaults:
            self.defaults.remove(item)
        super().__delitem__(item)
    @mlock
    def get(self, item: str, default: typing.Any = None, insert_default: bool = True) -> typing.Any:
        '''
            Gets an item, returning `default` if its not set
                If `insert_default` is true, and the item is not set, then runs `.default(item, default)`
        '''
        if item not in self.data:
            if insert_default:
                self.default(item, default)
            return default
        val = self.data[item]
        if (item in self.defaults) and (val != default):
            val = default
            if insert_default: self.default(item, default)
        return val
    @mlock
    def default(self, item: str, val: typing.Any, override: bool = True):
        '''
            Sets a default for an item and marks it as such
                Refuses to override a non-default value without `override`
        '''
        if (item in self.data) and (item not in self.defaults) and not override:
            raise KeyError(f'Cannot set default for existing non-default {item!r} without override')
        self.data[item] = val
        self.defaults.add(item)

    @mlock
    def update(self, other: typing.Self, *, remove: bool = False, keep: bool = True):
        '''
            Updates this instance with config from `other`
            Removes fields in this instance that aren't in `other` if `remove` is true
            If `keep` is true, then this instance's values are preferred to `other`'s
                If its a default in this instance, but not a default in `other`, it is overwritten anyway
        '''
        missing = object()
        for k in self.keys() | other.keys():
            s = self.data.get(k, missing)
            o = other.data.get(k, missing)
            assert not (s is o is missing)
            if s is missing:
                if k in other.defaults: self.default(k, o)
                else: self[k] = o
                continue
            if o is missing:
                if remove: del self[k]
                continue
            if k in self.defaults:
                if k not in other.defaults: self[k] = o
                elif not keep: self.default(k, o)
                continue
            if k in other.defaults: continue
