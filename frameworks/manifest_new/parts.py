#!/bin/python3

'''
    Parts of manifests

    Each part contains data, a name, and various helper methods
    Different types of manifests may use different parts
'''

#> Imports
import types
import typing
from functools import partial
from dataclasses import dataclass, field, asdict
#</Imports

#> Header >/
# Parts base
class BasePart:
    '''A no-op class that serves to only tie manifest parts together and for `isinstance()` checks'''
class UnstructuredBasePart[*ContentTypes](BasePart):
    '''A base part for allowing a manifest part to contain variable data'''
    def __init__(self, **kwargs: typing.Union[*ContentTypes]):
        self.__dict__.update(kwargs)
## Sub-values for make_part
_mutable_part_dataclass_decor = dataclass(kw_only=True, slots=True)
_part_dataclass_decor = dataclass(frozen=True, kw_only=True, slots=True)
## Manifest part decorator maker
def make_struct_part(name: str | None = None, add_to_all: list[str] | None = None, *, mutable: bool = True, bases: tuple[type, ...] = (BasePart,),
                     dc_decor: typing.Callable[[type[BasePart]], type[BasePart]] | None = None, post_init: typing.Callable[[type[BasePart]], None] | None = None) -> typing.Callable[[type[BasePart]], type[BasePart]]:
    '''
        Makes a decorator for a manifest-part, applying dataclass decorators and adding the `BasePart` superclass if it isn't already added

        If `dc_decor` is specified, then `mutable` is ignored
    '''
    assert (name is None) or isinstance(name, str), f'Field "name" must be a string or None' \
                                                    f'{", this function should be called to construct a decorator (`@make_struct_part(...)`), not as a decorator (`@make_struct_part`)" if isinstance(name, type) else ""}'
    def part_maker(cls: type[BasePart] | type) -> type[BasePart]:
        partcls = ((_mutable_part_dataclass_decor if mutable else _part_dataclass_decor) if dc_decor is None else dc_decor)(
            type((cls.__name__ if name is None else name), (cls,)+bases, cls.__dict__ | ({} if post_init is None else {'__post__init__': post_unit})))
        if add_to_all is not None: add_to_all.append(cls.__name__)
        return partcls
    return part_maker
def make_unstruct_part(name: str, add_to_all: list[str] | None = None, type_params: type = (typing.Any,), *, all_name: str | None = None, mutable: bool = True, base: type = UnstructuredBasePart) -> type[UnstructuredBasePart]:
    '''Makes a new type that inherits from `base[*type_params]`'''
    cls = types.new_class(name, (base[*type_params],), {} if mutable else {'__setattr__': None})
    if add_to_all is not None: add_to_all.append(name if all_name is None else all_name)
    return cls
# Setup __all__
__all__ = ['make_struct_part', 'make_unstruct_part', 'BasePart', 'UnstructuredBasePart']
_make_part = partial(make_struct_part, add_to_all=__all__)

# Parts classes
@_make_part('!id') # use special characters to delimit most important parts
class IDManifestPart:
    who:  str = field(kw_only=False)
    when: int = field(kw_only=False)
    what: str | None = None

# Finalize __all__
__all__ = tuple(__all__)

class test(UnstructuredBasePart): pass
