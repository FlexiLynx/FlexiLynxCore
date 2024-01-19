#!/bin/python3

#> Imports
import sys
import typing
from copy import deepcopy
from types import ModuleType
from collections import UserDict
from collections.abc import KeysView, ValuesView, ItemsView
from importlib import import_module
from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
from importlib.machinery import ModuleSpec
#</Imports

#> Header >/
__all__ = ('TFlexiSpace', 'DictUnion', 'DictJoiner')

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
    @typing.no_type_check # required for TypeGuard
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
            return type(self)(*self.dicts, *(d for d in other.dicts if d not in self.dicts), # join self.dicts and other.dicts
                              default_set_dict=getattr(self, '_default_set_dict', None), op_all=self.op_all)
        if isinstance(other, dict):
            return self.__reduce__() | other
        return NotImplemented
    def __ror__(self, other: dict | typing.Self) -> dict | typing.Self:
        if isinstance(other, type(self)):
            return type(self)(*other.dicts, *(d for d in self.dicts if d not in other.dicts), # join other.dicts and self.dicts
                              default_set_dict=getattr(self, '_default_set_dict', None), op_all=self.op_all)
        if isinstance(other, dict):
            return other | self.__reduce__()
        return NotImplemented
    def __ior__(self, other: dict | typing.Self) -> typing.Self:
        if isinstance(other, type(self)):
            self.dicts[:] = other.dicts + [d for d in self.dicts if d not in other.dicts]
        else: self.dicts.insert(0, other)
        return self

    # Overriden dict methods
    def clear(self):
        for d in self.dicts: d.clear()
    ## Getting
    def keys(self) -> set[typing.Hashable]:
        return set(k for k,v in self.items())
    def values(self) -> tuple[typing.Any]:
        return tuple(k for k,v in self.items())
    def items(self) -> tuple[tuple[typing.Hashable, typing.Any], ...]:
        return tuple(self.iitems())

    # Standalone methods
    def iitems(self) -> typing.Generator[tuple[typing.Hashable, typing.Any], None, None]:
        '''Not thread-safe'''
        seen = set()
        for d in self.dicts:
            yield from ((k,v) for k,v in d.items() if k not in seen)
            seen.update(d.keys())

    # Copy methods
    copy = __reduce__
    def __copy__(self) -> typing.Self:
        return type(self)(*map(dict.copy, self.dicts), default_set_dict=getattr(self, '_default_set_dict', None), op_all=self.op_all)
    def __deepcopy__(self, memo: dict = {}) -> typing.Self:
        copy = type(self).__new__(type(self))
        memo[id(self)] = copy
        return type(self)(*(deepcopy(d, memo) for d in self.dicts),
                          default_set_dict=deepcopy(getattr(self, '_default_set_dict', None), memo), op_all=self.op_all)
class DictJoiner(DictUnion):
    '''Similar to `DictUnion`, but offers methods to aggressively synchronize each sub-dict'''
    __slots__ = ()

    def __init__(self, *dicts: dict, sync_on_init: bool = True, init_force_order: bool = True):
        super().__init__(*dicts, op_all=True)
        if sync_on_init: self.sync(init_force_order)
    def sync(self, force_order: bool = False):
        items = self.items()
        if force_order: self.clear()
        for k,v in items: self[k] = v

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
    def find_spec(self, fullname: str, path: str | None, target: str | None = None) -> ModuleSpec | None:
        if fullname.split('.')[0] != self.flexispace._FS_key_[0]: return None
        return spec_from_loader(fullname, self.loader)

class TFlexiSpace(ModuleType):
    '''
        Provides a way to recursively define and use namespaces as importable modules

        Important note: packages assimilated to FlexiSpaces should make *very* careful use of relative importing of eachother
            While imports may work, they may not be pointing to the expected value
    '''
    __slots__ = ('_FS_dict_', '_FS_initialized_', '_FS_assimilate_', '_FS_metafinder_', '_FS_parents_', '_FS_key_', '_FS_assimilated_')

    __FS_sys_is_finalizing = sys.is_finalizing # keep reference even if `sys` name is collected

    __FS_ASSIMILATE            = 0b0001
    __FS_ASSIMILATE_INTRUSIVE  = 0b0010
    __FS_ASSIMILATE_AGGRESSIVE = 0b0100
    __FS_ASSIMILATE_LAZY       = 0b1000

    _FS_DEBUG_ASSIMILATE = False

    def __init__(self, name: str, doc: str | None = None, *, _parent: typing.Self | None = None, _dict: dict | None = None,
                 assimilate: bool = False, intrusive_assimilate: bool = True, aggressive_assimilate: bool = True,
                 assimilate_lazy_modules: bool = True):
        self._FS_dict_ = DictJoiner(self.__dict__) if _dict is None else DictJoiner(self.__dict__, _dict)
        if _parent is None:
            self._FS_parents_ = ()
            self._FS_key_ = (name,)
            self._FS_metafinder_ = FlexiSpaceFinder(self)
            sys.meta_path.append(self._FS_metafinder_)
            self._FS_assimilate_ = assimilate * (self.__FS_ASSIMILATE
                                                 + (self.__FS_ASSIMILATE_INTRUSIVE  * intrusive_assimilate)
                                                 + (self.__FS_ASSIMILATE_AGGRESSIVE * aggressive_assimilate)
                                                 + (self.__FS_ASSIMILATE_LAZY       * assimilate_lazy_modules))
            self.__package__ = None
        else:
            self._FS_parents_ = _parent._FS_parents_+(_parent,)
            self._FS_key_ = _parent._FS_key_+(name,)
            self._FS_metafinder_ = None
            if assimilate: raise TypeError('Cannot set attribute "assimilate" on a non-root FlexiSpace')
            self.__package__ = '.'.join(self._FS_key_[:-1])
        self._FS_initialized_ = True
        super().__init__('.'.join(self._FS_key_), doc)
        self._FS_dict_.sync(True)
    def __del__(self):
        if self.__FS_sys_is_finalizing() or (self._FS_metafinder_ is None): return
        sys.meta_path.remove(self._FS_metafinder_)
    def __setattr__(self, attr: str, val: typing.Any, *, _no_assimilate: bool = False):
        if not getattr(self, '_FS_initialized_', False):
            super().__setattr__(attr, val)
            return
        if (not _no_assimilate) and isinstance(val, ModuleType):
            if (~self)._FS_assimilate_ and (not isinstance(val, self.__class__)):
                val = self._assimilate(val, attr)
            sys.modules[f'{self.__name__}.{attr}'] = val
        self._FS_dict_[attr] = val

    def _aggressive_assimilate(self, mod: ModuleType, as_: str, doc: str | None) -> typing.Self:
        '''Creates a new `TFlexiSpace` from `mod`, then combines their dictionaries with `DictJoiner`'''
        new = type(self).__new__(type(self))
        new.__init__(as_, doc, _parent=self, _dict=mod.__dict__)
        return new
    def _intrusive_assimilate_val(self, obj: object, attr: str, val: object):
        '''Sets an attribute of an object (if possible)'''
        try: object.__setattr__(attr, val)
        except Exception: pass
        else: return
        try: super(type(v), v).__setattr__(attr, val)
        except Exception: pass
    def _assimilate(self, mod: ModuleType, as_: str) -> typing.Self:
        '''Converts a `ModuleType` into a `TFlexiSpace`'''
        if ((~self)._FS_assimilate_ & self.__FS_ASSIMILATE_AGGRESSIVE):
            amod = self._aggressive_assimilate(mod, as_, getattr(mod, '__doc__', None))
        else:
            amod = type(self)(as_, getattr(mod, '__doc__', None), _parent=self)
        public = set(getattr(mod, '__all__', set()))
        for a,v in mod.__dict__.items():
            if a not in public:
                if ((~self)._FS_assimilate_ & self.__FS_ASSIMILATE_INTRUSIVE) \
                       and isinstance(v, ModuleType) and not isinstance(v, self.__class__) \
                       and v.__name__.startswith(f'{self._FS_key_[0]}.') \
                       and (tree := (~self)._get_tree(v.__name__.split('.')[1:], create=False)) is not None:
                    v = tree
                amod.__setattr__(a, v, _no_assimilate=True)
                continue
            if isinstance(v, ModuleType) and not isinstance(v, self.__class__):
                v = amod._assimilate(v, a) # recursively assimilate public sub-modules (that aren't FlexiSpace modules)
            elif ((~self)._FS_assimilate_ & self.__FS_ASSIMILATE_INTRUSIVE) and (getattr(v, '__module__', None) == mod.__name__):
                amod._intrusive_assimilate_val(v, '__module__', self.__name__)
            super(type(self), amod).__setattr__(a, v)
        if self._FS_DEBUG_ASSIMILATE:
            super(type(self), amod).__setattr__('_FS_assimilated_', (self, mod, as_, {
                'public': public,
                'level': (~self)._FS_assimilate_,
            }))
        return amod

    def _get_tree(self, key: str | typing.Sequence[str], create: bool = True) -> typing.Self | None:
        '''Gets (or creates, if missing and `create`) a sub-FlexiSpace, creating all parents that are missing (if `create` is true)'''
        branch = self
        for n in (key.split('.') if isinstance(key, str) else key):
            if not hasattr(branch, n):
                if not create: return None
                setattr(branch, n, self.__class__(n, _parent=branch))
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

class _LazyFSModule(ModuleType):
    '''
        ! Currently broken and not implemented !

        Allows "lazily" including modules in a `FlexiSpace`, simply by setting this to a name:
            `lazymod = LazyFSModule('.lazymod', __package__)`
        This module can be realized in one of two ways:
            The recommended way is to reference it from its parent `TFlexiSpace`, which immediately realizes it:
                `root.parent.lazymod` realizes `lazymod` and returns a `TFlexiSpace`
            The second way is through attribute access or dir-ing:
                `lazymod.a`, `lazymod.a = 0`, `dir(lazymod)`
            In the second case, `lazymod` will still be a `LazyFSModule`, but will pass attributes (relatively) seamlessly (subsequent imports/access will get the real module as above)
        When this module is realized, a number of things happen:
          - The actual module is imported
          - If the module was added to a `TFlexiSpace` with `assimilate=True` and `assimilate_lazy_modules=True`, then the `LazyFSModule` in that space is replaced with the underlying module
              The underlying module will be assimilated as normal
          - The `LazyFSModule` joins its dictionary to the imported or assimilated module's dictionary (using `DictJoiner`)
    '''
    __slots__ = ('_attached_to', '_attached_as', '_realized', '_dict')

    def __init__(self, name: str, package: str | None = None):
        super().__setattr__('_dict', None)
        super().__setattr__('__name__', name)
        super().__setattr__('__package__', package)
        super().__setattr__('_attached_to', None)
        super().__setattr__('_attached_as', None)
        super().__setattr__('_realized', None)
        sys.modules[f'{package or ""}{name}'] = self
    def _realize(self) -> ModuleType:
        if (mod := super().__getattribute__('_realized')) is not None: return mod
        mod = import_module(self.__name__, self.__package__)
        if self._attached_to is not None:
            setattr(self._attached_to, self._attached_as, mod) # assimilates the module
            mod = getattr(self._attached_to, self._attached_as)
            super().__setattr__('_realized', mod)
            super().__setattr__('__name__', mod.__name__)
            super().__setattr__('__package__', mod.__package__)
        else: super().__setattr__('_realized', mod)
        super().__setattr__('_dict', DictJoiner(mod.__dict__, self.__dict__))
        sys.modules[f'{mod.__package__ or ""}{mod.__name__}'] = mod
        return self._realized
    def __getattr__(self, attr: str) -> typing.Any:
        return getattr(self._realize(), attr)
    def __setattr__(self, attr: str, val: typing.Any):
        if self._dict is not None:
            self._dict[attr] = val
        else: setattr(self._realize(), attr, val)
    def __dir__(self) -> typing.Sequence[str]:
        return dir(self._realize())

    def __repr__(self) -> str:
        if self._realized is None:
            return f'<unrealized LazyFSModule {self.__name__ if self.__package__ is None else f"{self.__package__}{self.__name__}"} / ' \
                   f'{"[unbound]" if self._attached_to is None else f"bound={self._attached_to}.{self._attached_as}"}>'
        return f'<realized LazyFSModule {self.__name__!r}' \
               f'{f" from {self.__file__}" if getattr(self, "__file__", None) is None else ""}>'
