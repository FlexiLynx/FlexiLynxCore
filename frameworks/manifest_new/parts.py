#!/bin/python3

'''
    Parts of manifests

    Each part contains data, a name, and various helper methods
    Different types of manifests may use different parts

    Note that, whilst `PartAttrContainer` is not in `__all__`, it is still considered a public symbol
'''

#> Imports
import types
import typing
import weakref
from functools import partial
from dataclasses import dataclass
#</Imports

#> Header >/
# Parts base
class BaseManifestPart:
    '''A no-op class that serves to only tie manifest parts together and for `isinstance()` checks'''
    __slots__ = ('_ipart',)
class PartAttrContainer:
    '''A class that serves as a container for part-class-related values (methods, etc.)'''
    __slots__ = ('_instance', '__dict__')
    _meth_pfx = '_ManifestPart_Method_'
    def __init__(self, instance: BaseManifestPart | None = None):
        super().__setattr__('_instance', None if instance is None else weakref.ref(instance))
        if instance is None: return
        for a,v in instance._cpart.__dict__.items():
            if a.startswith(self._meth_pfx): super().__setattr__(a.removeprefix(self._meth_pfx), types.MethodType(v, instance))
            elif f'{self._meth_pfx}{a}' in instance._cpart.__dict__: continue # don't overwrite previously bound methods with the unbound versions
            else: super().__setattr__(a, v)
    def __setattr__(self, attr: typing.Never, val: typing.Never): raise TypeError(f'Should not set attributes on a {type(self).__name__}')
class _PartAttrDescriptor:
    '''Allows redirecting to either instance or class-level `PartAttrContainer`s'''
    __slots__ = ()
    def __get__(self, instance: BaseManifestPart | None, type_: type[BaseManifestPart]) -> PartAttrContainer:
        return type_._cpart if instance is None else instance._ipart
## Sub-values for make_part
_mutable_part_dataclass_decor = dataclass(kw_only=True, slots=True, weakref_slot=True)
_part_dataclass_decor = dataclass(frozen=True, kw_only=True, slots=True, weakref_slot=True)
def _part_post_init(self: type[BaseManifestPart]): self._ipart = PartAttrContainer(self)
## Manifest part decorator maker
def make_part(name: str | None = None, add_to_all: list[str] | None = None, *, mutable: bool = True, bases: tuple[type, ...] = (BaseManifestPart,),
              dc_decor: typing.Callable[[type[BaseManifestPart]], type[BaseManifestPart]] | None = None, post_init: typing.Callable[[type[BaseManifestPart]], None] = _part_post_init) -> typing.Callable[[type[BaseManifestPart]], type[BaseManifestPart]]:
    '''
        Makes a decorator for a manifest-part, applying dataclass decorators and adding the `BaseManifestPart` superclass if it isn't already added
        Moves `cls.part_...` class variables (and methods, etc.) to a `cls.part` `PartAttrContainer`

        If `dc_decor` is specified, then `mutable` is ignored

        Note that the decorator's returned class does *not* inherit from the original class, rather extracting data from its `__dict__`
            (if needed, bases can be set in the `bases` parameter, but ensure that `BaseManifestPart` is in there!)
        Note that the decorator should not be used on a class that has any bases, as the returned class only subclasses `BaseManifestPart`
    '''
    assert (name is None) or isinstance(name, str), f'Field "name" must be a string or None' \
                                                    f'{", this function should be called to construct a decorator (`@make_part(...)`), not as a decorator (`@make_part`)" if isinstance(name, type) else ""}'
    def part_maker(cls: type[BaseManifestPart]) -> type[BaseManifestPart]:
        part = PartAttrContainer()
        cdict = {'part': _PartAttrDescriptor(), '_cpart': part,
                 '__annotations__': cls.__annotations__ | {'part': typing.ClassVar[PartAttrContainer]},
                 '__post_init__': _part_post_init} | {a: v for a,v in cls.__dict__.items() if not a.startswith('part_')}
        partcls = ((_mutable_part_dataclass_decor if mutable else _part_dataclass_decor) if dc_decor is None else dc_decor)(
            type((cls.__name__ if name is None else name), bases, cdict))
        for a,v in cls.__dict__.items():
            if not a.startswith('part_'): continue
            if isinstance(v, types.FunctionType): # instance methods are bound later
                object.__setattr__(part, f'{PartAttrContainer._meth_pfx}{a.removeprefix("part_")}', staticmethod(v))
            elif isinstance(v, classmethod): v = v.__get__(None, partcls) # bind the classmethod
            object.__setattr__(part, a.removeprefix('part_'), v)
        if add_to_all is not None: add_to_all.append(cls.__name__)
        return partcls
    return part_maker

# Setup __all__
__all__ = ['make_part', 'BaseManifestPart']
_make_part = partial(make_part, add_to_all=__all__)

# Parts classes

# Finalize __all__
__all__ = tuple(__all__)
