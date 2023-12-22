#!/bin/python3

#> Imports
import os
import shlex
import typing
from pathlib import Path
from ast import literal_eval
from collections import UserDict
#</Imports

#> Header >/
__all__ = ('EnvConfig',)

class EnvConfig(UserDict):
    'A read-only, case-insensitive namespace/dictionary that is populated by an environment variable or .flynx.env file'
    __slots__ = ('_envvar', '_type', '_rawenv', '_is_frozen')
    def __init__(self, var: str, type_: type | typing.Callable[[str], typing.Any] = literal_eval, freeze: bool = True):
        self.__is_frozen = False
        self._envvar = var
        self._type = type_
        self._rawenv = os.getenv(self._envvar, '')
        if (p := Path(f'./{self._envvar}.flynx.env')).is_file():
            self._rawenv += f' {p.readtext()}'
        self.__dict__ = {k.lower(): self._type(v) for k,v in (kv.split('=', 1)
                                                  for kv in shlex.split(self._rawenv))}
        self.data = self.__dict__
        if freeze: self._is_frozen = True

    def __setitem__(self, item: str, value: typing.Any):
        if getattr(self, '_is_frozen', False):
            raise TypeError(f'{self.__class__.__qualname__} is frozen')
        super().__setattr__(item, value)
    __setattr__ = __setitem__

    def __repr__(self) -> str:
        return f'{self.__class__.__qualname__}({self._envvar!r}, {self.__dict__!r})'
