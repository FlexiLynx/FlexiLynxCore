#!/bin/python3

#> Imports
import io
import re
import json
from ast import literal_eval
from configparser import ConfigParser

from .ManifestCore import Manifest, man_packer
from .ManifestTypes import *
#</Imports

#> Header >/
__all__ = ('render_pack', 'load_packed', 'render_json', 'load_json', 'render_ini', 'load_ini')

def render_pack(m: Manifest) -> bytes:
    return m.pack()
def load_packed(p: bytes) -> Manifest:
    return Manifest.from_dict(man_packer.unpack(packed))

JSON_ARRAY_CLEANER_A = re.compile(r'^(\s*"[^"]*":\s*)(\[[^\]]*\])(,?\s*)$', re.MULTILINE)
JSON_ARRAY_CLEANER_B = staticmethod(lambda m: m.group(1)+(re.sub(r'\s+', '', m.group(2)).replace(',', ', '))+m.group(3))
def render_json(m: Manifest, *, compact: bool = False) -> bytes:
    return self.JSON_ARRAY_CLEANER_A.sub(self.JSON_ARRAY_CLEANER_B,
                                         json.dumps(m.as_dict(), sort_keys=False) if compact else json.dumps(m.as_dict(), sort_keys=False, indent=4))
def load_json(j: bytes) -> Manifest:
    return Manifest.from_dict(json.loads(j.decode()))

def render_ini(m: Manifest) -> bytes:
    p = ConfigParser(interpolation=None); p.optionxform = lambda o: o
    for ok,ov in m.as_dict().items():
        if ov is None: continue
        p[ok] = {ik: repr(iv) for ik,iv in ov.items()}
    with io.StringIO() as stream:
        p.write(stream)
        return stream.getvalue().encode()
def load_ini(i: bytes) -> Manifest:
    p = ConfigParser(interpolation=None); p.optionxform = lambda o: o
    with io.StringIO(i.decode()) as stream:
        p.read_string(stream.getvalue())
    return Manifest.from_dict({k: {ik: literal_eval(iv) for ik,iv in v.items()} for k,v in p.items() if k != 'DEFAULT'})
