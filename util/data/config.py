#!/bin/python3

'''
    Provides very basic JSON-based configuration for FlexiLynx, in a not-super-readable format
        It is recommended to suggest that end-users install a module that provides configuration options
'''

#> Imports
import json
import typing
from pathlib import Path
from copy import deepcopy
from threading import RLock
from collections import UserDict

from . import packlib
from ..text import base85
from ..flatten import flatten_map, extrude_map
from ..parallel import mlock
#</Imports

#> Header >/
__all__ = ('Config',)

json_serializable = (dict, list, tuple, str, int, float, bool, type(None))

class Config(UserDict):
    __slots__ = ('data', 'path', 'defaults', '_lock')

    def __init__(self, path: Path | None):
        self.data = {}
        self.set_path(path)
        self.defaults = set()
        self._lock = RLock()
    def set_path(self, path: Path | None):
        '''Sets `.path` and creates its parents if needed'''
        self.path = path
        if self.path is not None:
            path.parent.mkdir(exist_ok=True, parents=True)

    @mlock
    def to_map(self, delim: str = '.', *, _data: dict | None = None) -> dict[str, typing.Any]:
        '''
            Converts a configuration instance to an extruded `dict`
                Does *not* populate the necessary `_metadata` fields or perform any conversions
        '''
        assert delim is not None
        return extrude_map(self.data if _data is None else _data, delim)
    @mlock
    def export_dict(self, delim: str = '.') -> typing.Mapping[str, typing.Any]:
        '''Exports this configuration instance to a dict suitable for JSON'''
        encoded = []
        packed = {}
        data = self.data.copy()
        for k,v in data.items():
            if isinstance(v, json_serializable): continue
            if isinstance(v, bytes):
                data[k] = base85.encode(v)
                encoded.append(k)
                continue
            if isinstance(v, typing.Iterable): # TODO: make iterables recursively check for encodable data
                data[k] = list(v)
                continue
            packed[k] = base85.encode(packlib.pack(data[k]))
            data[k] = '<packed>'
        return self.to_map(delim, _data=data) | {
            '_metadata': {
                'defaults': list(self.defaults),
                'encoded': encoded,
                'packed': packed,
            },
        }
    @mlock
    def export(self, delim: str = '.', *, indent=4, **json_config) -> str:
        '''Exports this configuration instance to JSON'''
        return json.dumps(self.export_dict(delim), indent=indent, **json_config)

    @mlock
    def postprocess(self, encoded: typing.Iterable[str], packed: dict[str, str]):
        '''Runs post-processing on this instance, decoding any keys in `encoded` and unpacking any keys in `packed`'''
        for k in encoded:
            self[k] = base85.decode(self[k])
        for k,v in packed.items():
            self[k] = packlib.unpack(base85.decode(v))[0]
    @classmethod
    def load_map(cls, m: typing.Mapping[str, typing.Any], delim: str = '.', *, metadata: typing.Mapping[str, typing.Any] | None = None,
                   instance: typing.Self | None = None, postprocess: bool = True) -> typing.Self:
        '''
            Converts a mapping `m` into a configuration instance
            If `metadata` is given, it is used instead of the `_metadata` field in `m`
            If `instance` is given, it is used instead of creating a new instance
            If `postprocess` is false, then encoded and packed entries are not decoded
        '''
        assert delim is not None
        self = cls(None) if instance is None else instance
        metadata = m['_metadata'] if metadata is None else metadata
        with self._lock:
            self.data = flatten_map({k: v for k,v in m.items() if k != '_metadata'}, delim)
            self.defaults = set(metadata['defaults'])
            if '_metadata' in self: del self.data['_metadata']
            self.postprocess(metadata['encoded'], metadata['packed'])
            return self
    @classmethod
    def load(cls, jsn: str, delim: str = '.') -> typing.Self: # .import() is invalid...
        '''Converts exported JSON `jsn` into a configuration instance'''
        return cls.load_map(json.loads(jsn), delim)

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
