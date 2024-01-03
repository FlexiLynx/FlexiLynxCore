#!/bin/python3

#> Imports
import sys
import typing
from functools import reduce
from types import ModuleType
from collections import UserDict
from collections.abc import KeysView, ValuesView, ItemsView
from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
from importlib.machinery import ModuleSpec
#</Imports

#> Header >/
__all__ = ('TFlexiSpace', 'DictUnion')

class DictUnion(UserDict):
    '''
        Allows accessing multiple dictionaries as one

        Similar concept to `collections.ChainMap`, but is somewhat lighter
    '''
    __slots__ = ('dicts', 'default_set_dict', '_default_set_dict', 'op_all')

    def __init__(self, *dicts: dict, default_set_dict: int | dict | None = -1, op_all: bool = False):
        self.dicts = list(dicts)
        self.op_all = op_all
        if not op_all:
            assert default_set_dict is not None, 'default_set_dict should only be None if op_all is True'
            self._default_set_dict = default_set_dict
            if isinstance(default_set_dict, int):
                self.default_set_dict = dicts[default_set_dict]
            else:
                self.default_set_dict = default_set_dict
    def _dict_containing(self, item: typing.Hashable, g_all: bool = False) -> dict | tuple[dict] | None:
        if g_all:
            return tuple(d for d in self.dicts if item in d) or None
        for d in self.dicts:
            if item in d: return d
        return None

    # Special methods
    ## Getting
    def __contains__(self, item: typing.Hashable) -> bool:
        return self._dict_containing(item) is not None
    def __getitem__(self, item: typing.Hashable) -> typing.Any:
        if (d := self._dict_containing(item)) is not None:
            return d[item]
        raise KeyError(item)
    ## Mutating
    def __setitem__(self, item: typing.Hashable, value: typing.Any):
        for d in (self.dicts if self.op_all else self._dict_containing(item, True)):
            d[item] = value
    def __delitem__(self, item: typing.Hashable):
        if ds := self._dict_containing(item, True):
            for d in ds: del d[item]
            return
        raise KeyError(item)
    ## Operators
    def __len__(self):
        return len(self.items())
    def __repr__(self) -> str:
        '''Note that this method is rather expensive!'''
        return repr(self.__reduce__())
    def __reduce__(self) -> dict:
        '''Reduces self to a basic dictionary'''
        return dict(self.items())
    ### | operators
    def __or__(self, other: dict | typing.Self) -> dict | typing.Self:
        if isinstance(other, type(self)):
            return type(self)(self.dicts + [d for d in other.dicts if d not in self.dicts], # join self.dicts and other.dicts
                              getattr(self, '_default_set_dict', None), self.op_all)
        if isinstance(other, dict):
            return self.__reduce__() | other
        return NotImplemented
    def __ror__(self, other: dict | typing.Self) -> dict | typing.Self:
        if isinstance(other, type(self)):
            return type(self)(other.dicts + [d for d in self.dicts if d not in other.dicts], # join other.dicts and self.dicts
                              getattr(self, '_default_set_dict', None), self.op_all)
        if isinstance(other, dict):
            return other | self.__reduce__()
        return NotImplemented
    def __ior__(self, other: dict | typing.Self) -> typing.Self:
        if isinstance(other, type(self)):
            self.dicts[:] = other.dicts + [d for d in self.dicts if d not in other.dicts]
        else: self.dicts.insert(0, other)
        return self

    # Overriden dict methods
    def keys(self) -> set[typing.Hashable]:
        return set(k for k,v in self.items())
    def values(self) -> tuple[typing.Any]:
        return tuple(k for k,v in self.items())
    def items(self) -> tuple[tuple[typing.Hashable, typing.Any]]:
        return tuple(self.iitems())

    # Standalone methods
    def iitems(self) -> typing.Generator[tuple[typing.Hashable, typing.Any], None, None]:
        '''Not thread-safe'''
        seen = set()
        for d in self.dicts:
            yield from ((k,v) for k,v in d.items() if k not in seen)
            seen.update(d.keys())

class FlexiSpaceLoader(Loader):
    __slots__ = ('flexispace',)

    def __init__(self, flexispace: 'TFlexiSpace'):
        self.flexispace = flexispace
    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return self.flexispace@spec.name.split('.')[1:]
    def exec_module(self, m: ModuleType): pass
class FlexiSpaceFinder(MetaPathFinder):
    __slots__ = ('flexispace', 'loader')
    def __init__(self, flexispace: 'TFlexiSpace'):
        self.flexispace = flexispace
        self.loader = FlexiSpaceLoader(flexispace)
    def find_spec(self, fullname: str, path: str, target: str | None = None) -> None:
        if fullname.split('.')[0] != self.flexispace._FS_key_[0]: return None
        return spec_from_loader(fullname, self.loader)

class TFlexiSpace(ModuleType):
    '''Provides a way to recursively define and use namespaces as importable modules'''
    __slots__ = ('_FS_initialized_', '_FS_assimilate_', '_FS_metafinder_', '_FS_parents_', '_FS_key_')

    __FS_sys_is_finalizing = sys.is_finalizing # keep reference even if `sys` name is collected

    __FS_ASSIMILATE            = 0b001
    __FS_ASSIMILATE_INTRUSIVE  = 0b010
    __FS_ASSIMILATE_AGGRESSIVE = 0b100

    def __init__(self, name: str, doc: str | None = None, *, _parent: typing.Self | None = None,
                 assimilate: bool = False, intrusive_assimilate: bool = True, aggressive_assimilate: bool = True):
        if _parent is None:
            self._FS_parents_ = ()
            self._FS_key_ = (name,)
            self._FS_metafinder_ = FlexiSpaceFinder(self)
            sys.meta_path.append(self._FS_metafinder_)
            self._FS_assimilate_ = assimilate * (self.__FS_ASSIMILATE
                                                 + (self.__FS_ASSIMILATE_INTRUSIVE  * intrusive_assimilate)
                                                 + (self.__FS_ASSIMILATE_AGGRESSIVE * aggressive_assimilate))
            self.__package__ = None
        else:
            self._FS_parents_ = _parent._FS_parents_+(_parent,)
            self._FS_key_ = _parent._FS_key_+(name,)
            self._FS_metafinder_ = None
            if assimilate: raise TypeError('Cannot set attribute "assimilate" on a non-root FlexiSpace')
            self.__package__ = '.'.join(self._FS_key_[:-1])
        self._FS_initialized_ = True
        super().__init__('.'.join(self._FS_key_), doc)
    def __del__(self):
        if self.__FS_sys_is_finalizing() or (self._FS_metafinder_ is None): return
        sys.meta_path.remove(self._FS_metafinder_)
    def __setattr__(self, attr: str, val: typing.Any):
        if isinstance(val, ModuleType) and getattr(self, '_FS_initialized_', False):
            if (~self)._FS_assimilate_ and (not isinstance(val, self.__class__)):
                val = self._assimilate(val, attr)
            sys.modules[f'{self.__name__}.{attr}'] = val
        super().__setattr__(attr, val)

    def _intrusive_assimilate(self, obj: type('HasDunderModule', (typing.Protocol,), {'__module__': ''})):
        '''Sets __module__ attributes of an object (if possible)'''
        try: obj.__module__ = self.__name__
        except Exception: pass
        else: return
        try: object.__setattr__('__module__', self.__name__) # try forceful override with base object
        except Exception: pass
        else: return
        try: super(type(v), v).__setattr__('__module__', self.__name__) # try forceful override with super type
        except Exception: pass
    def _assimilate(self, mod: ModuleType, as_: str) -> typing.Self:
        '''Converts a `ModuleType` into a `TFlexiSpace`'''
        amod = type(self)(as_, getattr(mod, '__doc__', None), _parent=self)
        if ((~self)._FS_assimilate_ & self.__FS_ASSIMILATE_AGGRESSIVE):
            raise NotImplementedError('Aggressive assimilate not yet implemented')
        public = set(getattr(mod, '__all__', set()))
        for a,v in mod.__dict__.items():
            if a not in public:
                super(type(self), amod).__setattr__(a, v)
                continue
            if isinstance(v, ModuleType) and not isinstance(v, self.__class__):
                v = amod._assimilate(v, a) # recursively assimilate public sub-modules (that aren't FlexiSpace modules)
            elif ((~self)._FS_assimilate_ & self.__FS_ASSIMILATE_INTRUSIVE) and (getattr(v, '__module__', None) == mod.__name__):
                amod._intrusive_assimilate(v)
            super(type(self), amod).__setattr__(a, v)
        return amod

    def _get_tree(self, key: str | tuple[str, ...]) -> typing.Self:
        '''Gets (or creates, if missing) a sub-FlexiSpace, creating all parents that are missing'''
        branch = self
        for n in (key.split('.') if isinstance(key, str) else key):
            if not hasattr(branch, n): setattr(branch, n, self.__class__(n, _parent=branch))
            branch = getattr(branch, n)
            assert isinstance(branch, self.__class__ | ModuleType)
        return branch
    __matmul__ = _get_tree # use @ operator as a shortcut
    def _get_branch(self, key: str) -> typing.Self:
        '''Gets a sub-FlexiSpace, creating it if it doesn't exist, otherwise asserting that it is an instance of self.__class__'''
        branch = getattr(self, key, None)
        if branch is None:
            branch = self.__class__(key, _parent=self)
            setattr(self, key, branch)
        else: assert isinstance(branch, self.__class__)
        return branch
    __truediv__ = _get_branch # use / operator for path-like shortcut
    def __pos__(self) -> typing.Self: # use + operator for parent shortcut
        '''Returns this FlexiSpace's parent'''
        return self._FS_parents_[-1]
    def _root(self) -> typing.Self:
        '''Returns this FlexiSpace's root'''
        if p := self._FS_parents_: return p[0]
        return self
    __invert__ = _root # use ~ operator for root shortcut
    def __xor__(self, n: int) -> typing.Self: # use ^ operator for n-parent shortcut (kinda like git)
        '''Returns the n-th parent, where -1 < n <= len(self._FS_parents_), n=0 is self, n=1 is self._FS_parents_[-1] and n=2 is self._FS_parents_[-2]'''
        if n == 0: return self
        assert -1 < n <= len(self._FS_parents_)
        return self._FS_parents_[-n]

    def __repr__(self) -> str:
        return f'<FlexiSpace module {".".join(self._FS_key_)!r}>'

    __Nameable = typing.runtime_checkable(type('Nameable', (typing.Protocol,), {'__annotations__': {'__name__': str}}))
    __Qualnameable = typing.runtime_checkable(type('Qualnameable', (typing.Protocol,), {'__annotations__': {'__qualname__': str}}))
    def __call__(self, obj: __Nameable | __Qualnameable) -> typing.Self:
        '''
            Adds an object that has a name attribute (__name__ or __qualname__) to this FlexiSpace
            Most useful when using an instance of this class as a decorator
        '''
        name = getattr(obj, '__name__', getattr(obj, '__qualname__', None))
        if name is None: raise TypeError(f'Object {obj} has no __name__ or __qualname__!')
        setattr(self, name, obj)
        return self
