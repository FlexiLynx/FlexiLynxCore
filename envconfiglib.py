#!/bin/python3

#> Imports
import os
import shlex
import typing
from pathlib import Path
from collections import UserDict
#</Imports

#> Header >/
__all__ = ('EnvConfig',)

class EnvConfig(UserDict):
    'A read-only, case-insensitive namespace/dictionary that is populated by an environment variable or .flynx.env file'
    __slots__ = ('_envvar', '_type', '_rawenv', '_is_frozen')

    def __init__(self, var: str, type_: type | typing.Callable[[str], typing.Any] = str, freeze: bool = True):
        self._envvar = var
        self._type = type_
        self._rawenv = os.getenv(self._envvar, '')
        if (p := Path(f'./{self._envvar}.flynx.env')).is_file():
            self._rawenv = f'{p.readtext()} {self._rawenv}'.strip()
        self.__dict__ = {k.lower(): self._type(v) for k,v in (kv.split('=', 1)
                                                  for kv in shlex.split(self._rawenv))
                         if not (k.startswith('_') or hasattr(self.__class__, k))}
        self.data = self.__dict__
        if freeze: self._is_frozen = True

    @staticmethod
    def _bool(v: str) -> bool:
        '''Converts a string into a boolean in a shell-like way ("" and "0" = False)'''
        return bool(v) and v != '0'
    def get_bool(self, k: str, default: str | bool = False) -> bool:
        '''Converts an key's item into a boolean in a shell-like way'''
        v = self.get(k, default)
        if isinstance(v, bool): return v
        if isinstance(v, str): return self._bool(v)
        return bool(v) # let other types resolve normally

    def __setitem__(self, item: str, value: typing.Any):
        if getattr(self, '_is_frozen', False):
            raise TypeError(f'{self.__class__.__qualname__} is frozen')
        super().__setattr__(item, value)
    __setattr__ = __setitem__

    def __repr__(self) -> str:
        return f'{self.__class__.__qualname__}({self._envvar!r})'
