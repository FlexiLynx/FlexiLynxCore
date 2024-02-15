#!/bin/python3

'''Global module-based utilities'''

#> Imports
import sys
import types
import typing
import inspect
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
from importlib.machinery import ModuleSpec
#</Imports

#> Header >/
__all__ = ('register_pseudomodule', 'unregister_pseudomodule', 'PseudoPackage')

# Pseudo modules
pseudomodules = {}

class PseudoModuleLoader(Loader):
    __slots__ = ()
    def create_module(self, spec: ModuleSpec) -> types.ModuleType:
        name = spec.name.split('.')
        mod = pseudomodules[name[0]]
        for n in name[1:]:
            if not hasattr(mod, n):
                raise ModuleNotFoundError(f'Error importing {spec.name}: {mod.__name__} has not attribute {n}')
            mod = getattr(mod, n)
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
    '''A simple module subclass that adds a null `__path__` attribute to allow package importing'''
    __slots__ = ()
    __path__ = None
