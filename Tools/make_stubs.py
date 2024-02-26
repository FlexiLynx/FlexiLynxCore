#!/bin/python3

from __future__ import annotations

#> Imports
import io
import re
import os
import sys
import time
import types
import typing
import inspect
import builtins
import itertools
from pathlib import Path
from functools import partial
from importlib import util as iutil
#</Imports

#> Header
eprint = partial(print, file=sys.stderr)

IMPORTS = re.compile(r'^(?:from ?(?P<from>[a-zA-Z][\w.]*) )?import (?P<imports>(?:[a-zA-Z][\w.]*(?: as [a-zA-Z]\w*)?(?:,\s*)?)+)$', re.MULTILINE)
NAME_DEFAULT = re.compile(r'(?P<front>\(|(?:,\s*))(?P<name>[a-zA-Z]\w*)(?P<annotation>:\s*[\[a-zA-Z].*?)\s*=\s*(?P<value>[a-zA-Z][\w\.]*?)(?P<back>\)|(?:\s*,))')

def stubify_function(f: types.FunctionType, into: typing.TextIO):
    into.write(f'# function stub: {f.__name__!r} #\n')
    #into.write(f'def {f.__name__}')
    #if f.__type_params__:
    #    into.write(f'[{", ".join(f.__type_params__)}]')
    #into.write(f'{inspect.signature(f)}:')
    lines = map(str.rstrip, inspect.getsourcelines(f)[0])
    lines_def = []
    for l in lines:
        lines_def.append(l)
        if l.endswith(':'): break
    lines_def = '\n'.join(lines_def)
    repl = []
    def on_name_default(m: re.Match) -> str:
        if hasattr(builtins, m.group('value')): # no replacement of builtins
            return m.group(0)
        repl.append((m.group('name'), m.group('annotation'), m.group('value')))
        return f'{m.group("front")}{m.group("name")}{"" if m.group("annotation") is None else f""": {m.group("annotation")} """}={" "*(m.group("annotation") is not None)}...{m.group("back")}'
    into.write(f'{NAME_DEFAULT.sub(on_name_default, lines_def)}')
    if getattr(f, '__doc__', None) is None:
        into.write(' pass')
    else:
        into.write(f"""\n    '''{f.__doc__}{"    "*f.__doc__.endswith("\n")}'''""")
    into.write('\n')
    if repl:
        into.write('    # Eliminated name-defaults:\n    # ')
        into.write('\n    # '.join(f'{n}{a or ""} = v' for n,a,v in repl))
        into.write('\n')
    #if f.__doc__ is None:
    #    into.write(' pass')
    #    return
    #into.write(f"\n    '''{f.__doc__}'''")
    
def stubify_module(m: types.ModuleType) -> tuple[str, dict[str, ...]]:
    subms = {}
    with io.StringIO() as body:
        body.write(f'## Stub: {m.__name__!r} ##\n\n')
        if (getattr(m, '__file__', None) is not None) and (mp := Path(m.__file__)).exists():
            for frm,imp in IMPORTS.findall(mp.read_text()):
                for stmt in map(str.strip, imp.split(',')):
                    name = stmt.split(' as ')[-1] if ' as ' in stmt else stmt
                    if name in m.__all__: continue
                    body.write(f'{f"from {frm} " if frm else ""}import {imp} # Name import: {name!r}\n')
        body.write(f'__all__ = {m.__all__!r}\n\n')
        for a,v in ((a, getattr(m, a)) for a in m.__all__):
            body.write(f'# {a!r} = {v!r}\n')
            if isinstance(v, types.ModuleType):
                if m.__package__ is not None: body.write('from . ')
                body.write(f'import {a} as {a}')
                subms[a] = v
            elif isinstance(v, types.FunctionType):
                stubify_function(v, body)
            else:
                body.write(f'{a}: {inspect.formatannotation(type(v), m)}')
            body.write('\n\n')
        body = body.getvalue()
    return (body, subms)
def stubify(mod: types.ModuleType, *, as_: str | None = None) -> dict[str, str]:
    if as_ is None: as_ = mod.__name__
    mods = {}
    mods[(as_,)],subms = stubify_module(mod)
    for n,m in subms.items():
        stsm = stubify(m, as_=n)
        mods[(as_, n)] = stsm[(n,)]
        mods |= {(as_,)+sn: sm for sn,sm in stsm.items() if sn}
    return mods
#</Header

#> Setup
# Setup base path
base = Path('./type-stubs/') #Path(f'./type-stubs/{int(time.time())}')
base.mkdir(exist_ok=True, parents=True)
eprint(f'Outputs will go to {base}')
# Fetch __entrypoint__
eprint('Fetching __entrypoint__')
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None): p = Path(ep)
elif (p := Path('__entrypoint__.py')).exists(): pass
elif (p := Path('../__entrypoint__.py')).exists(): pass
else:
    raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py, maybe set FLEXILYNX_ENTRYPOINT in env?')
sys.path.append(p.parent.as_posix())
__entrypoint__ = iutil.spec_from_file_location('__entrypoint__', p.as_posix()) \
                     .loader.load_module()
# Run __init__ and __setup__
eprint('exec __init__()')
__entrypoint__.__init__()
eprint('exec __setup__()')
__entrypoint__.__setup__()
# Import FlexiLynx
import FlexiLynx
#</Setup

#> Main >/
mods = stubify(FlexiLynx)
modnames = sorted(mods.keys())
nested = set()
for i,mn in enumerate(modnames):
    if ((mn == '.') or # root is nested by default
       (i >= len(modnames)-1)): continue # can't get last
    if len(mn) > len(modnames[i+1]): continue
    if mn[-1] == modnames[i+1][len(modnames[i])-1]:
        nested.add(mn)
for n,m in mods.items():
    p = base/n[0] if len(n) == 1 else base/Path(*n[1:])
    p.parent.mkdir(exist_ok=True, parents=True)
    if (n in nested) and (len(n) > 1):
        p.mkdir(exist_ok=True, parents=True)
        (p/'__init__.pyi').write_text(m)
    else:
        p.with_suffix('.pyi').write_text(m)
