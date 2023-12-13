#!/bin/python3

#> Imports
import os
import shlex
import typing
from pathlib import Path
from ast import literal_eval
from collections import UserDict

#import FlexiLynx
#</Imports

#> Header >/
class EnvConfig(UserDict):
    'A read-only, case-insensitive dictionary that is populated by an environment variable or .flynx.env file'
    __slots__ = ('envvar', 'type', 'rawenv')
    def __init__(self, var: str, type_: type | typing.Callable[[str], typing.Any] = literal_eval):
        self.envvar = var
        self.type = type_
        self.rawenv = os.getenv(self.envvar, '')
        if (p := Path(f'./{self.envvar}.flynx.env')).is_file():
            self.rawenv += f' {p.readtext()}'
        self.data = {k: literal_eval(v) for k,v in (kv.split('=', 1) for kv in shlex.split(self.rawenv))}
    
#FlexiLynx.core.
deepconfig = type('DeepConfig', (UserDict,), {
    '__slots__': (),
    '__init__': lambda self: setattr(self, 'data', {keyval.split('=', 1)[0]: literal_eval(keyval.split('=', 1)[1]) for keyval in shlex.split(os.getenv(envvar, ''))}),
    '__doc__': f'A read-only, case-insensitive dictionary that is populated by the `{envvar}` environment variable',
    '__getitem__': lambda self, attr: self.data[attr.lower()],
    '__setitem__': NotImplemented,
    '__repr__': lambda self: f'{self.__class__.__qualname__}({UserDict.__repr__(self)})',
})()
