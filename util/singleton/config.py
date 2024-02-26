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

from .. import base85, pack
from ..parallel import mlock
from ..tools.functools import defaults, DEFAULT
from ..tools.flattools import flatten_map, extrude_map
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
                Does *not* populate the necessary `_defaults` field or perform any conversions
        '''
        assert delim is not None
        return extrude_map(self.data if _data is None else _data, delim)

    DATA_PFX         = '\x00'
    DATA_PFX_ESC     = '\x00\x00'
    DATA_SUFF        = ':'
    DATA_PFX_ENCODED = f'{DATA_PFX}b85{DATA_SUFF}'
    DATA_PFX_PACKED  = f'{DATA_PFX}packed{DATA_SUFF}'

    @mlock
    def export_dict(self, delim: str = '.') -> typing.Mapping[str, typing.Any]:
        '''Exports this configuration instance to a dict suitable for JSON'''
        def safe_v(v: object) -> object:
            if isinstance(v, json_serializable):
                if isinstance(v, str) and v.startswith(self.DATA_PFX):
                    return f'{self.DATA_PFX_ESC}{v[len(self.DATA_PFX):]}'
                return v
            if isinstance(v, typing.Mapping):
                return safe_dict(dict(v))
            if isinstance(v, bytes):
                return f'{self.DATA_PFX_ENCODED}{base85.encode(v)}'
            if isinstance(v, typing.Iterable):
                return list(map(safe_v, v))
            return f'{self.DATA_PFX_PACKED}{base85.encode(packlib.pack(v))}'
        def safe_dict(d: dict) -> typing.Iterator[tuple[str, typing.Any]]:
            for k,v in d.items(): yield (k, safe_v(v))
        return self.to_map(delim, _data=dict(safe_dict(self.data))) | {
            '_defaults': list(self.defaults),
        }
    @mlock
    @defaults(export_dict)
    def export(self, delim: str = DEFAULT, *, indent=4, **json_config) -> str:
        '''Exports this configuration instance to JSON'''
        return json.dumps(self.export_dict(delim), indent=indent, **json_config)

    @mlock
    def postprocess(self):
        '''Runs post-processing on this instance, decoding any encoded or packed values'''
        for k,v in self.data.items():
            if not isinstance(v, str): continue
            if not v.startswith(self.DATA_PFX): continue
            if v.startswith(self.DATA_PFX_ESC):
                self.data[k] = f'{self.DATA_PFX}{v[len(self.DATA_PFX_ESC):]}'
            elif v.startswith(self.DATA_PFX_ENCODED):
                self.data[k] = base85.decode(v.split(self.DATA_SUFF, 1)[1])
            elif v.startswith(self.DATA_PFX_PACKED):
                self.data[k] = packlib.unpack(base85.decode(v.split(self.DATA_SUFF, 1)[1]))[0]
            else:
                raise ValueError(f'Found DATA_PFX {self.DATA_PFX!r}, but with an unknown reason, in key {k!r}\n value: {v!r}')
    @classmethod
    @defaults(export_dict)
    def load_map(cls, m: typing.Mapping[str, typing.Any], delim: str = DEFAULT, *, defaults: typing.Mapping[str, typing.Any] | None = None,
                   instance: typing.Self | None = None, postprocess: bool = True) -> typing.Self:
        '''
            Converts a mapping `m` into a configuration instance
            If `defaults` is given, it is used instead of the `_defaults` field in `m`
            If `instance` is given, it is used instead of creating a new instance
            If `postprocess` is false, then encoded and packed entries are not decoded
        '''
        assert delim is not None
        self = cls(None) if instance is None else instance
        defaults = m.get('_defaults', {}) if defaults is None else defaults
        with self._lock:
            self.data = flatten_map({k: v for k,v in m.items() if k != '_defaults'}, delim)
            self.defaults = set(defaults)
            if '_defaults' in self: del self.data['_defaults']
            self.postprocess()
            return self
    @classmethod
    @defaults(export_dict)
    def load(cls, jsn: str, delim: str = DEFAULT) -> typing.Self: # .import() is invalid...
        '''Converts exported JSON `jsn` into a configuration instance'''
        return cls.load_map(json.loads(jsn), delim)

    @classmethod
    def loadf(cls, f: typing.TextIO | Path) -> typing.Self:
        '''Loads an instance of self from a file or path `f`'''
        self = cls.load(f.read_text() if isinstance(f, Path) else f.read())
        if isinstance(f, Path):
            self.path = f
        elif (((p := getattr(f, 'name', None)) is not None)
              and (p := Path(p)).exists()):
            self.path = p
        return self
    @mlock
    def save(self, f: typing.TextIO | Path | None = None):
        '''
            Saves this class to `f`
                `f` can be a file or `Path`, or `None`
                If `f` is `None`, the configured path (`self.path`) is used
                    If `self.path` is `None`, `TypeError` is thrown
        '''
        if f is None: f = self.path
        if f is None:
            raise TypeError('This instance was not configured with a path, so one must be provided')
        if isinstance(f, Path):
            f.write_text(self.export())
        else:
            f.write(self.export())

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
