#!/bin/python3

'''Global module-based utilities'''

#> Imports
import sys
import types
import typing
import inspect
from importlib import import_module
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
from importlib.machinery import ModuleSpec

from .functools import reach
from .. import logger
#</Imports

#> Header >/
__all__ = ('register_pseudomodule', 'unregister_pseudomodule', 'PseudoPackage', 'deferred_import')

# Pseudo modules
pseudomodules = {}

pslogger = logger.core_logger.getChild('pseudomod')
class PseudoModuleLoader(Loader):
    __slots__ = ()
    def create_module(self, spec: ModuleSpec) -> types.ModuleType:
        name = spec.name.split('.')
        pslogger.trace(f'Import: {name!r}')
        mod = pseudomodules[name[0]]
        for i,n in enumerate(name[1:]):
            pslogger.trace(f'{".".join(name[:i+1])}: {mod!r}')
            if not hasattr(mod, n):
                raise ModuleNotFoundError(f'Error importing {spec.name}: {mod.__name__} has no attribute {n}')
            mod = getattr(mod, n)
        pslogger.trace(f'{".".join(name)}: {mod!r}')
        return mod
    def exec_module(self, mod: types.ModuleType): pass
class PseudoModuleHook(MetaPathFinder):
    __slots__ = ('loader',)
    def __init__(self):
        self.loader = PseudoModuleLoader()
    def find_spec(self, fullname: str, path: typing.Any, target: str | None = None) -> ModuleSpec:
        return spec_from_loader(fullname, self.loader) if fullname.split('.')[0] in pseudomodules else None
metafinder = PseudoModuleHook()
sys.meta_path.append(metafinder)

def register_pseudomodule(name_or_mod: str | types.ModuleType, mod: types.ModuleType | None = None, *, override: bool = False):
    '''
        Registers a module to be importable from anywhere
        Refuses to overwrite another module unless `override` is set
        If `name_or_mod` and `mod` are given, `mod` is saved as `name`
        Otherwise, `name_or_mod` should be a module and its `__name__` is used
    '''
    if isinstance(name_or_mod, str):
        if mod is None:
            raise TypeError('If name_or_mod is a string, then mod should ot be supplied')
        if (name_or_mod in pseudomodules) and not override:
            raise RuntimeError('Refusing to override an existing pseudo-module when override is false')
        pseudomodules[name_or_mod] = mod
    else:
        if mod is not None:
            raise TypeError('If name_or_mod is not a string, then mod should not be supplied')
        if (name_or_mod.__name__ in pseudomodules) and not override:
            raise RuntimeError('Refusing to override an existing pseudo-module when override is false')
        pseudomodules[name_or_mod.__name__] = name_or_mod
def unregister_pseudomodule(name_or_mod: str | types.ModuleType) -> types.ModuleType:
    '''
        Unregisters and returns a previously registered pseudo-module
            `name_or_mod` can be a string, or a module, in which case its `__name__` is used, similarly to `register_pseudomodule()`
        Raises `KeyError` if the module isn't registered
    '''
    return pseudomodules.pop(name_or_mod if isinstance(name_or_mod, str) else name_or_mod.__name__)

class PseudoPackage(types.ModuleType):
    '''
        A simple module subclass that adds a `__path__` property that lists everything in `__slots__` and `__dict__`
            to allow for package searching
    '''
    __slots__ = ()
    @property
    def __path__(self) -> list[str]:
        return tuple(self.__dict__.keys()) + self.__slots__

# Deferred imports
class deferred_import(types.ModuleType):
    '''
        Allows deferring the import of a module until it is accessed
        The `stack_reacher` parameter allows the module to replace its name in the caller's frame in some situations when it is imported
    '''
    __slots__ = ('_deferred_name', '_deferred_package', '_deferred_stack_reacher', '_deferred_module')

    def __init__(self, name: str, package: str | None = None, *, stack_reacher: bool = True):
        super().__setattr__('_deferred_name', name)
        super().__setattr__('_deferred_package', package)
        super().__setattr__('_deferred_stack_reacher', stack_reacher)
        super().__setattr__('_deferred_module', None)
        if f'{package or ""}{name}' in sys.modules:
            self._deferred_realize()
        else:
            sys.modules[f'{package or ""}{name}'] = self

    def _deferred_realize(self, stack_reach: bool | None = None) -> types.ModuleType:
        if stack_reach is None: stack_reach = self._deferred_stack_reacher
        if self._deferred_module is not None:
            return self._deferred_module
        if sys.modules[f'{self._deferred_package or ""}{self._deferred_name}'] is not self:
            super().__setattr__('_deferred_module', sys.modules[f'{self._deferred_package or ""}{self._deferred_name}'])
        else:
            del sys.modules[f'{self._deferred_package or ""}{self._deferred_name}']
            super().__setattr__('_deferred_module', import_module(self._deferred_name, self._deferred_package))
        if stack_reach:
            # replace this module with the real one in the caller's globals and locals
            out = reach(2) # reach out twice, once to get to the operator (__init__, __get/set/delattr__, __dir__) and the second time for its caller
            for n,g in out.f_globals.items():
                if g is not self: continue
                out.f_globals[n] = self._deferred_module
            for n,l in out.f_locals.items():
                if l is not self: continue
                out.f_locals[n] = self._deferred_module
        return self._deferred_module

    def __getattr__(self, attr: str) -> typing.Any:
        return getattr(self._deferred_realize(), attr)
    def __setattr__(self, attr: str, val: typing.Any):
        setattr(self._deferred_realize(), attr, val)
    def __delattr__(self, attr: str):
        delattr(self._deferred_realize(), attr)
    def __dir__(self) -> list[str]:
        return dir(self._deferred_realize())

    def __repr__(self) -> str:
        return (f'<deferred module {f"""{self._deferred_package or ""}{self._deferred_name}"""!r}'
                f'{"" if self._deferred_module is None else " realized"}'
                f'{" stack-reacher" if self._deferred_stack_reacher else ""}>')
