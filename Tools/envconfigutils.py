#!/bin/python3

#> Imports
import os
import sys
import click
import shlex
import typing
from pathlib import Path
from importlib import util as iutil
from ast import literal_eval
#</Imports

# Get entrypoint
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None): p = Path(ep)
elif (p := Path('__entrypoint__.py')).exists(): pass
elif (p := Path('../__entrypoint__.py')).exists(): pass
else:
    raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py, maybe set FLEXILYNX_ENTRYPOINT in env?')
sys.path.append(p.parent.as_posix())
__entrypoint__ = iutil.spec_from_file_location('__entrypoint__', p.as_posix()) \
                     .loader.load_module()

#> Header
__entrypoint__.__init__()
from FlexiLynx.core.envconfiglib import EnvConfig

types = {'str': (str, str), 'int': (int, int.__repr__), 'bool': (bool, lambda b: repr(int(b))), 'literal': (literal_eval, repr)}
#</Header

#> Main >/
@click.command(context_settings={'help_option_names': ('-h', '--help', '-?'), 'max_content_width': 160})
@click.argument('env')
@click.argument('output', type=click.File('w'), default='-')
@click.option('--type', 'type_', type=click.Choice(types.keys()), help='What type each env-key is', default='str')
@click.option('--no-newline', help='Deliminate each option with spaces instead of newlines', is_flag=True, default=False)
def cli(*, env: str, output: typing.TextIO, type_: typing.Literal[*types.keys()], no_newline: bool):
    '''
        Exports an EnvConfig from an environment variable (and ENV.flynx.env) into a file or stdout

        Note that this *WILL* source from ENV.flynx.env files the same way EnvConfig always does

        ENV is the name of the EnvConfig to create

        OUTPUT is where to write the file (defaults to stdout)
    '''
    type_ = types[type_]
    ec = EnvConfig(env, type_=type_[0], freeze=True)
    data = (f'{shlex.quote(k)}={shlex.quote(type_[1](v))}'
            for k,v in object.__getattribute__(ec, 'data').items()
            if k != 'data')
    print(*data, sep=(' ' if no_newline else '\n'), end=('' if no_newline else '\n'), file=output)

cli()
