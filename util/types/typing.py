#!/bin/python3

'''Typehint-related utilities that are not in the built-in `typing` module'''

#> Imports
import typing
#</Imports

#> Header >/
__all__ = ('Protocol',
           'Orderable_lt', 'Orderable_gt', 'Orderable')

# Protocols
def Protocol(_name: str, _doc: str | None = None, _module='<xProtocol>', _rtime_checkable: bool = True, _bases: tuple[type, ...] = (typing.Protocol,), **annotations) -> type[typing.Protocol]:
    '''
        Creates a new `typing.Protocol` class
            Sets `__doc__` to `_doc` and `__module__` to `_module`
        Annotations are set using keyword arguments
    '''
    prot = type(_name, _bases, {'__annotations__': annotations,
                                '__doc__': _doc, '__module__': _module})
    if _rtime_checkable:
        return typing.runtime_checkable(prot)
    return prot
## Ordering
Orderable_lt = Protocol('Orderable_lt',
                        '''Any object with a `<` operator as a `__lt__()` method''',
                        __lt__=typing.Callable[[typing.Self, typing.Self], bool | typing.Any])
Orderable_gt = Protocol('Orderable_gt',
                        '''Any object with a `>` operator as a `__gt__()` method''',
                        __gt__=typing.Callable[[typing.Self, typing.Self], bool | typing.Any])
Orderable = typing.Union[Orderable_lt, Orderable_gt]
