#!/bin/python3

#> Imports
import io
import os
import sys
import click
import typing
from pathlib import Path
from functools import wraps
from importlib import util as iutil
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
from FlexiLynx.core.frameworks.blueprint import *

def h_output(out: typing.TextIO, b: Blueprint):
    click.echo('Cannot check if blueprint is dirty: NOT IMPLEMENTED', file=sys.stderr)
    click.echo(f'Wrote {out.write(b.serialize())} byte(s) to {getattr(out, "name", "?")}', file=sys.stderr)
def h_input(inp: typing.TextIO) -> Blueprint:
    d = inp.read()
    click.echo(f'Read {len(d)} byte(s) from {getattr(inp, "name", "?")}', file=sys.stderr)
    return Blueprint.deserialize(d)
def w_output(c):
    @click.option('--output', type=click.File('w'), help='The file to write to (defaults to stdout)', default='-', show_default=False)
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_output(*, output: typing.TextIO, **kwargs):
        h_output(output, c(**kwargs))
    return c_w_output
def w_input(c):
    @click.argument('blueprint', type=click.File('r'))
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_input(*, blueprint: typing.TextIO, **kwargs):
        c(blueprint=h_input(blueprint), **kwargs)
    return c_w_input
def w_io(c):
    @click.argument('blueprint', type=click.File('r'))
    @click.option('--output', type=click.File('w'), help='The file to write to (defaults to overwriting the input, pass "-" to write to stdout)', default=None, show_default=False)
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_io(*, blueprint: typing.TextIO, output: typing.TextIO | None, **kwargs):
        blue = c(blueprint=h_input(blueprint), **kwargs)
        if output is None:
            if blueprint.fileno() == sys.stdin.fileno():
                output = sys.stdout
            else:
                blueprint.truncate(0)
                blueprint.seek(0, io.SEEK_SET)
                output = blueprint
        if isinstance(blue, Blueprint): blue = blue.serialize()
        output.write(blue)
    return c_w_io
#</Header

#> Main >/
cli = click.Group(context_settings={'help_option_names': ('-h', '--help', '-?'), 'max_content_width': 160})

# Generate commands #
gencli = click.Group('gen', help='Generation commands')
cli.add_command(gencli)
# gen blueprint
@gencli.command()
@click.argument('id')
@click.argument('files', type=Path, nargs=-1)
@click.option('-n', '--name', help='The human-readable name of this blueprint')
@click.option('-d', '--desc', help='A human-readable description of this blueprint\'s contents', default=None)
@click.option('-v', '--version', help='The human-readable (machine-irrelevant) version of this blueprint', default=None)
@click.option('-u', '--url', help='The URL that this blueprint should check for updates from', default=None)
@click.option('-U', '--file-url', help='The URL that the main content (files) are updated from', default=None)
@click.option('-D', '--dep', help='The ID of another blueprint that this blueprint depends on', multiple=True)
@click.option('-C', '--conf', help='The ID of another blueprint that this blueprint conflicts with', multiple=True)
@click.option('--hash-method', help='The name of the hash function to use', default='sha1')
@click.option('--root', help='The root to use as the relative path for files', type=Path, default=Path('.'))
@w_output
def blueprint(*, id: str, files: typing.Sequence[Path],
              name: str, desc: str | None, version: str | None,
              url: str | None, file_url: str | None,
              dep: typing.Sequence[str], conf: typing.Sequence[str],
              hash_method: str,
              root: Path) -> Blueprint:
    return Blueprint(id=id, rel=0,
                     name=name, desc=desc, version=version,
                     url=url,
                     main=generate.make_manifest(file_url, *files, root=root, hash_method=hash_method), drafts=None,
                     crypt=parts.Crypt(key=None, sig=None, cascade={}),
                     relations=parts.Relations(depends=dep, conflicts=conf))
# Add commands #
addcli = click.Group('add', help='Adding commands')
cli.add_command(addcli)
# add files
@addcli.command()
@w_io
@click.argument('files', type=Path, nargs=-1)
@click.option('-t', '--to', metavar='draft', help='Add the file(s) to a draft instead', default=None)
@click.option('--root', help='The root to use as the relative path for files', type=Path, default=Path('.'))
def files(blueprint: Blueprint, *, files: typing.Sequence[Path], to: str | None, root: Path) -> Blueprint:
    if to is None: to = blueprint.main
    else: to = blueprint.drafts[to]
    to.files |= generate.hash_files(root, tuple(f.relative_to(root).as_posix() for f in files), hash_method=to.hash_method)
    return blueprint
# add draft
@addcli.command()
@w_io
@click.argument('draft-id')
@click.argument('files', type=Path, nargs=-1)
@click.option('-u', '--url', help='The URL that this pack will fetch artifacts from', default=None)
@click.option('--hash-method', help='The name of the hash function to use', default='sha1')
@click.option('--root', help='The root to use as the relative path for files', type=Path, default=Path('.'))
@click.option('--overwrite', help='Allow overwriting an existing draft', is_flag=True, default=False)
def draft(blueprint: Blueprint, *, draft_id: str, files: typing.Sequence[Path], url: str | None, hash_method: str, root: Path, overwrite: bool):
    if (draft_id in blueprint.drafts):
        if not overwrite:
            raise Exception(f'Refusing to overwrite existing draft {draft_id!r} when --overwrite was not supplied')
        click.echo(f'WARNING: overwriting existing draft {draft_id!r}', file=sys.stderr)
    blueprint.drafts[draft_id] = generate.make_manifest(url, *files, root=root, hash_method=hash_method)
    return blueprint

# Main
if __name__ == '__main__': cli()
