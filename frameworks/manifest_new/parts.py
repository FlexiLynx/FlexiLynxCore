#!/bin/python3

'''
    Parts of manifests

    Each part contains data, a name, and various helper methods
    Different types of manifests may use different parts

    Note that, whilst `@make_part()` and `BaseManifestPart` are not in `__all__`, they are considered public symbols
'''

#> Imports
import typing
from dataclasses import dataclass
#</Imports

#> Header >/
class PartAttrContainer:
    '''A no-op class that serves as a container for part-class-related values (methods, etc.)'''
class BaseManifestPart:
    '''A no-op class that serves to only tie manifest parts together and for `isinstance()` checks'''
    __slots__ = ()

_mutable_part_dataclass_decor = dataclass(kw_only=True, slots=True, weakref_slot=True)
_part_dataclass_decor = dataclass(frozen=True, kw_only=True, slots=True, weakref_slot=True)
def make_part(name: str | None = None, *, mutable: bool = True, dc_decor: typing.Callable[[type[BaseManifestPart]], type[BaseManifestPart]] | None = None) -> typing.Callable[[type[BaseManifestPart]], type[BaseManifestPart]]:
    '''
        Makes a decorator for a manifest-part, applying dataclass decorators and adding the `BaseManifestPart` superclass if it isn't already added
        Moves `cls.part_...` class variables (and methods, etc.) to a `cls.part` `PartAttrContainer`

        If `dc_decor` is specified, then `mutable` is ignored

        Note that the decorator's returned class does *not* inherit from the original class, rather extracting data from its `__dict__`
        Note that the decorator should not be used on a class that has any bases, as the returned class only subclasses `BaseManifestPart`
    '''
    assert (name is None) or isinstance(name, str), f'Field "name" must be a string or None' \
                                                    f'{", this function should be called to construct a decorator (`@make_part(...)`), not as a decorator (`@make_part`)" if isinstance(name, type) else ""}'
    def part_maker(cls: type[BaseManifestPart]) -> type[BaseManifestPart]:
        part = PartAttrContainer()
        return ((_mutable_part_dataclass_decor if mutable else _part_dataclass_decor) if dc_decor is None else dc_decor)(
            type((cls.__name__ if name is None else name), (BaseManifestPart,), {
                'part': part,
                '__annotations__': cls.__annotations__ | {'part': typing.ClassVar[PartAttrContainer]},
            } | {a: v for a,v in cls.__dict__.items() if (not a.startswith('part_')) or (setattr(part, a.removeprefix('part_'), v))})
        )
    return part_maker
