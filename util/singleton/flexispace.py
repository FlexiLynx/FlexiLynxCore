#!/bin/python3

'''Adds an import-friendly namespace-as-module system'''

#> Imports
import types
import typing

from ..tools import moduletools
#</Imports

#> Header >/
__all__ = ('FlexiSpace',)

_NOT_SET = object()

class SubFlexiSpace(moduletools.PseudoPackage):
    '''A class for subvalues of `FlexiSpace`s'''
    __slots__ = ()

    def __init__(self, name: str, doc: str | None = None):
        super().__init__(name, doc)
    def __matmul__(self, key: str | typing.Sequence[str]) -> typing.Self:
        if not key: return self
        if isinstance(key, str): key = key.split('.')
        cur = self
        for k in key:
            cur = getattr(self, k, _NOT_SET)
            if cur is _NOT_SET:
                cur = SubFlexiSpace(k)
                setattr(self, k, cur)
                cur.__package__ = f'{self.__package__ or "~"}.{self.__name__}'
            self = cur
        return cur
    def __repr__(self) -> str:
        return f'<FlexiSpace sub {f"""{self.__package__ or "~"}.{self.__name__}"""!r}>'
class FlexiSpace(moduletools.PseudoPackage):
    '''
        Provides a namespace-as-a-module
            Top-level `FlexiSpace`s are added to the pseudo-modules list using `moduletools.register_pseudomodule()`
    '''
    __slots__ = ()

    SubFlexiSpace = SubFlexiSpace

    def __init__(self, name: str, doc: str | None = None, *, importable: bool = True):
        if importable:
            moduletools.register_pseudomodule(name, self)
        super().__init__(name, doc)
    def __matmul__(self, key: str | typing.Sequence[str]) -> typing.Self | SubFlexiSpace:
        if not key: return self
        if isinstance(key, str): key = key.split('.')
        cur = getattr(self, key[0], _NOT_SET)
        if cur is _NOT_SET:
            cur = self.SubFlexiSpace(key[0])
            setattr(self, key[0], cur)
            cur.__package__ = self.__name__
        return cur@(key[1:])
    def __repr__(self) -> str:
        return f'<FlexiSpace top {self.__name__!r}>'
