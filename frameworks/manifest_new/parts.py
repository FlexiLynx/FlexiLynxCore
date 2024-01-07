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
    __slots__ = ()

    p_subparts: typing.ClassVar[typing.Mapping | None] = None

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

    @classmethod
    def _p_import_val(cls, k: str, v: typing.Any) -> typing.Any:
        '''
            Converts values for importing

            In `BasePart`, this either converts sub-part mappings to sub-parts, or returns `v` with no changes
                A value is converted into a sub-part if `p_subparts` exists and is not `None` and contains `k` (and `p_subparts[k]` is not `None`)
                    with the equivalent of `p_subparts[k].import(v)`
        '''
        if isinstance(v, cabc.Mapping) and (cls.p_subparts is not None) and ((sp := cls.p_subparts.get(k, None)) is not None):
            return sp.p_import(v)
        return v
    @classmethod
    def _p_import_map(cls, d: typing.Mapping) -> typing.Self:
        '''Creates an instance of this part-class using a mapping, translating values with `_p_import_val(key, val)`'''
        return cls(**{k: cls._p_import_val(k, v) for k,v in d.items()})
    @classmethod
    def p_import(cls, export: typing.Mapping[str, [bool | int | float | complex | bytes | str | typing.Sequence | typing.Set | typing.Mapping | None]]) -> typing.Self:
        '''
            Converts an exported mapping into an instance of this part-class
            Creates sub-parts using the `p_subparts` mapping if it exists
            The following methods are used:
              - The top-level part is created with `_p_import_map(export)`
              - Values are translated with `_p_import_val(key, val)`
              - Sub-parts are created with `<SubPartClass>.p_import(sub_part_map)`
        '''
        return cls._p_import_map(export)

class UnstructuredBasePart[*ContentTypes](BasePart):
    '''A base part for allowing a manifest part to contain variable data'''
    def __init__(self, **kwargs: typing.Union[*ContentTypes]):
        self.__dict__.update(kwargs)
## Sub-values for make_part
_mutable_part_dataclass_decor = dataclass(kw_only=True, slots=True)
_part_dataclass_decor = dataclass(frozen=True, kw_only=True, slots=True)
## Manifest part decorator maker
def make_struct_part(name: str | None = None, add_to_all: list[str] | None = None, *, mutable: bool = True, auto_subparts: bool = True,
                     bases: tuple[type, ...] = (BasePart,), dc_decor: typing.Callable[[type[BasePart]], type[BasePart]] | None = None, post_init: typing.Callable[[type[BasePart]], None] | None = None) -> typing.Callable[[type[BasePart]], type[BasePart]]:
    '''
        Makes a decorator for a manifest-part, applying dataclass decorators and adding the `BasePart` superclass if it isn't already added
            Also generates the `p_subparts` mapping (as a `mappingproxy`) if `auto_subparts` is true
                Subparts are added to (copied) existing `p_subparts` mappings
                Subparts are discovered via annotations, although detection is limited:
                    it will only check if an annotation is a subpart,
                    or has an `__args__` attribute that contains a subpart class (A.E. `<subpart class> | None`),
                        but only if its `__origin__` is not `typing.ClassVar` (so, ignores class variable types),
                        (asserts that only one subpart is in `__args__`)

        If `dc_decor` is specified, then `mutable` is ignored
    '''
    assert (name is None) or isinstance(name, str), f'Field "name" must be a string or None' \
                                                    f'{", this function should be called to construct a decorator (`@make_struct_part(...)`), not as a decorator (`@make_struct_part`)" if isinstance(name, type) else ""}'
    def part_maker(cls: type[BasePart] | type) -> type[BasePart]:
        cdict = cls.__dict__.copy()
        if post_init is not None: cdict['__post_init__'] = post_init
        if auto_subparts:
            cdict['p_subparts'] = dict(cdict.get('p_subparts', ()))
            for n,a in cls.__annotations__.items():
                if getattr(a, '__origin__', None) is typing.ClassVar: continue # skip ClassVars
                if isinstance(a, type) and issubclass(a, BasePart): cdict['p_subparts'][n] = a # base annotation, <name>: <partcls>
                elif not hasattr(a, '__args__'): continue
                else: # nested in an annotation
                    if not (ps := tuple(i for i,av in enumerate(a.__args__) if isinstance(av, type) and issubclass(av, BasePart))): continue
                    assert len(ps) == 1, f'Cannot specify multiple `BasePart` subclasses in a single type: saw {tuple(p.__qualname__ for p in ps)} in annotation {a!r}'
                    cdict['p_subparts'][n] = a.__args__[ps[0]]
            cdict['p_subparts'] = types.MappingProxyType(cdict['p_subparts'])
        partcls = ((_mutable_part_dataclass_decor if mutable else _part_dataclass_decor) if dc_decor is None else dc_decor)(
            type((cls.__name__ if name is None else name), (cls,)+bases, cdict))
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
