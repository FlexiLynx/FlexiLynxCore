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
from collections import abc as cabc
from collections.abc import Iterable, Iterator, Set, Mapping
#</Imports

#> Header >/
# Parts base
class BasePart:
    '''A base class for all manifest parts'''

    @classmethod
    def _p_export_val(cls, v: typing.Any) -> bool | int | float | complex | bytes | str | tuple | frozenset | types.MappingProxyType | None:
        '''
            Exports values into immutable primitives and/or collections in the following order:
                (note that the number next to each item groups items where order is non-important in an implementation
                (for instance, in any implementation, handing exporting to `v.[_]p_export()` should always be done first)
             1) Hands the work of exporting over to `v._p_export()` or `v.p_export()` if `v` has either of those methods
             2) Returns (non-`bool`) constants (`None`, `NotImplemented`, and `Ellipsis`/`...`) directly
             2) Returns primitives (`bool`, `int`, `float`, `complex`, `str`, and `bytes`)
                    Primitives are first passed to their own constructor to reduce subclasses to an immutable state
                    Note that `bytearray` is also captured, and is reduced to `bytes`
                    Note that `bool` should be checked before `int`, as `bool` is a subclass of `int`
             3) Hands over mappings (`collections.abc.Mapping`) to `_p_export_dict()`
             3) Hands over sequences (`collections.abc.Sequence`) to `_p_export_iterable()` and converts it to a `tuple`
             3) Hands over sets (`collections.abc.Set`) to `_p_export_iterable()` and converts it to a `frozenset`
             4) Tries to `return _p_export_unknown(v)`, if it exists (and is not `None`), so that subclasses can add that method
                    `_p_export_unknown()` should raise `TypeError` if it can't deal with the type
            If an unknown value is encountered, then it is handed to `_p_export_unknown()` (if it exists and is not `None`)
                If `_p_export_unknown()` cannot handle the type, or is not set, then `TypeError` is raised
                    (`_p_export_unknown()` should raise the `TypeError` at its own discretion)
        '''
        if (sfunc := (getattr(v, '_p_export', None) or getattr(v, 'p_export', None))) is not None:
            return sfunc()
        match v:
            # return constants directly
            ## types are used in the pattern below because NotImplemented and Ellipsis are seen as names
            case (None | types.NotImplementedType() | types.EllipsisType()): return v
            # return primitives, ensure that they are reduced to primitives in cases of subclasses
            case bool(): return bool(v)
            case int(): return int(v)
            case float(): return float(v)
            case complex(): return complex(v)
            case bytes() | bytearray(): return bytes(v)
            case str(): return str(v)
            # handle mappings and sequences
            case cabc.Mapping():
                return types.MappingProxyType(dict(cls._p_export_dict(v)))
            case cabc.Sequence():
                return tuple(cls._p_export_iterable(v))
            case cabc.Set():
                return frozenset(cls._p_export_iterable(v))
        if (ufunc := getattr(cls, '_p_export_unknown', None)) is not None:
            try: return ufunc(v)
            except TypeError as e:
                raise TypeError(f'Cannot export unknown type {type(v).__qualname__!r} of value {v!r}: _p_export_unknown() raised {e!r}')
        raise TypeError(f'Cannot export unknown type {type(v).__qualname__!r} of value {v!r} (and _p_export_unknown is not defined)')
    @classmethod
    def _p_export_iterable(cls, v: typing.Iterable) -> typing.Iterable:
        '''
            Exports an iterable using `_p_export_val()` on each value
            Note that an assertion is made to prevent iterators themselves from being exported,
                as exporting a partially completed iterator could cause hard-to-find issues
        '''
        assert not isinstance(v, cabc.Iterator), 'Refusing to export an iterator as it may lead to unpredictable results'
        return (cls._p_export_val(vv) for vv in v)
    @classmethod
    def _p_export_dict(cls, d: dict) -> typing.Iterable[tuple[str, bool | int | float | complex | bytes | str | tuple | frozenset | types.MappingProxyType | None]]:
        '''
            Exports a dictionary into an iterable of `(key, _p_export_val(val))` tuples
                Ignores all keys that start with `P_`, `p_`, or `_`
        '''
        return ((k, cls._p_export_val(v)) for k,v in d.items())
    def p_export(self) -> types.MappingProxyType[str, [bool | int | float | complex | bytes | str | tuple | frozenset | types.MappingProxyType | None]]:
        '''
            Converts this part into a dictionary (`mappingproxy`) of primitive and immutable types
            Values beginning with `p_`, `P_`, or `_` should not be exported
            If a value has a `._p_export()` or `.p_export()` method, that should be used to export the object
                No further processing should be done on that value
                `.p_export()` should be used to export a part directly, `._p_export()` is to override exporting specifically for nested exports
            If a subclass of `BasePart` wants to only modify exporting of a specific *type* of value, then the `_p_export_val()` classmethod can be overridden
                It is recommended to `return super()._p_export_val(v)` on types not recognized by the overriden method
                    or at the very least `return mappingproxy(dict(v.p_export()))` or `return mappingproxy(dict(v.p_export()))` if `v` has either of those methods,
                        `return mappingproxy(dict(_p_export_dict(v)))` for mappings (`mappingproxy` is `types.MappingProxyType`),
                        `return frozenset(_p_export_iterable(v))` for sets,
                        and `return tuple(_p_export_iterable(v))` for otherwise unhandled sequences
            Note that structured parts should have immutable values anyway (`dict`s are an exception as there is no built-in frozen version)
        '''
        return types.MappingProxyType(dict(self._p_export_dict(asdict(self))))
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
