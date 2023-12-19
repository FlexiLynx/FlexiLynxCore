#!/bin/python3

#> Imports
import sys
import typing
from types import ModuleType
from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
from importlib.machinery import ModuleSpec
#</Imports

#> Header >/
__all__ = ('TFlexiSpace',)

class FlexiSpaceLoader(Loader):
    __slots__ = ('flexispace',)
    def __init__(self, flexispace: 'TFlexiSpace'):
        self.flexispace = flexispace
    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return self.flexispace
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
    __slots__ = ('_FS_metafinder_', '_FS_parents_', '_FS_key_')

    def __init__(self, name: str, doc: str | None = None, *, _parent: typing.Self | None = None):
        if _parent is None:
            self._FS_parents_ = ()
            self._FS_key_ = (name,)
            self._FS_metafinder_ = FlexiSpaceFinder(self)
            sys.meta_path.append(self._FS_metafinder_)
        else:
            self._FS_parents_ = _parent._FS_parents_+(_parent,)
            self._FS_key_ = _parent._FS_key_+(name,)
            self._FS_metafinder_ = None
            self.__package__ = '.'.join(self._FS_key_[:-1])
        super().__init__('.'.join(self._FS_key_), doc)
    def __del__(self):
        if self._FS_metafinder_ is None: return
        sys.meta_path.remove(self._FS_metafinder_)
    def __setattr__(self, attr: str, val: typing.Any):
        if isinstance(val, ModuleType):
            sys.modules[f'{self.__name__}.{attr}'] = val
        super().__setattr__(attr, val)

    def _get_tree(self, key: str | tuple[str]) -> typing.Self:
        '''Gets (or creates, if missing) a sub-FlexiSpace, creating all parents that are missing'''
        branch = self
        for n in (key.split('.') if isinstance(key, str) else key):
            if not hasattr(branch, n): setattr(branch, n, self.__class__(n, _parent=branch))
            branch = getattr(branch, n)
            assert isinstance(branch, self.__class__)
        return branch
    __matmul__ = _get_tree # use @ operator as a shortcut
    def _get_branch(self, key: str) -> typing.Self:
        '''Gets a sub-FlexiSpace, creating it if it doesn\'t exist, otherwise asserting that it is an instance of self.__class__'''
        branch = getattr(self, key, None)
        if branch is None:
            branch = self.__class__(key, _parent=self)
            setattr(self, key, branch)
        else: assert isinstance(branch, self.__class__)
        return branch
    __truediv__ = _get_branch # use / operator for path-like shortcut
    def __invert__(self) -> typing.Self: # use ~ operator for parent shortcut
        '''Returns this FlexiSpace's parent'''
        return self._FS_parents_[-1]
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
