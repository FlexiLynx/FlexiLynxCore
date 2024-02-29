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
__entrypoint__.__load__()
__entrypoint__.__setup__()
from FlexiLynx.core.frameworks.blueprint import *

def h_warn_key(b: Blueprint):
    if b.crypt.key is None:
        click.echo('This blueprint does not hold a key, it is recommended to sign it', file=sys.stderr)
    elif not b.verify(no_exc=True):
        click.echo('This blueprint is dirty, it is recommended to sign it', file=sys.stderr)
def h_output(out: typing.TextIO, b: Blueprint):
    h_warn_key(b)
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
        h_warn_key(blue)
        if isinstance(blue, Blueprint): blue = blue.serialize()
        if output is not None:
            click.echo(f'Wrote {output.write(blue)} byte(s) to {getattr(output, "name", "?")}', file=sys.stderr)
        elif blueprint.fileno() == sys.stdin.fileno():
            click.echo(f'Wrote {sys.stdout.write(blue)} byte(s) to <stdout>', file=sys.stderr)
        else:
            click.echo(f'Wrote {Path(blueprint.name).write_text(blue)} byte(s) to {blueprint.name}', file=sys.stderr)
    return c_w_io
#</Header

#> Main >/
cli = click.Group(context_settings={'help_option_names': ('-h', '--help', '-?'), 'max_content_width': 160})

# Multi-group commands #
@click.command()
@click.option('--output', type=click.File('wb'), help='The file to write the key to (defaults to stdout)', default='-')
def m_genkey(*, output: typing.BinaryIO):
    output.write(crypt.EdPrivK.generate().private_bytes_raw())

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
@click.option('--hash-method', help='The name of the hash function to use', default=DEFAULT_HASH_ALGORITHM)
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
# gen key
gencli.add_command(m_genkey, 'key')

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
@click.option('--hash-method', help='The name of the hash function to use', default=DEFAULT_HASH_ALGORITHM)
@click.option('--root', help='The root to use as the relative path for files', type=Path, default=Path('.'))
@click.option('--overwrite', help='Allow overwriting an existing draft', is_flag=True, default=False)
def draft(blueprint: Blueprint, *, draft_id: str, files: typing.Sequence[Path], url: str | None, hash_method: str, root: Path, overwrite: bool) -> Blueprint:
    if (draft_id in blueprint.drafts):
        if not overwrite:
            raise Exception(f'Refusing to overwrite existing draft {draft_id!r} when --overwrite was not supplied')
        click.echo(f'WARNING: overwriting existing draft {draft_id!r}', file=sys.stderr)
    blueprint.drafts[draft_id] = generate.make_manifest(url, *files, root=root, hash_method=hash_method)
    return blueprint

# Crypt commands #
cryptcli = click.Group('crypt', help='Blueprint signing and verifying')
cli.add_command(cryptcli)
# crypt genkey
cryptcli.add_command(m_genkey, 'genkey')
# crypt sign
@cryptcli.command()
@w_io
@click.argument('key', type=click.File('rb'))
def sign(blueprint: Blueprint, *, key: typing.BinaryIO) -> Blueprint:
    blueprint.sign(crypt.EdPrivK.from_private_bytes(key.read()), test=False)
    return blueprint
# crypt verify
@cryptcli.command()
@w_input
@click.option('--key', help='Alternate key to verify with', type=click.File('rb'), default=None)
@click.option('--key-is-public', help='Treat the alternate key provided with --key as a public key, not a private key', is_flag=True, default=False)
def verify(blueprint: Blueprint, *, key: typing.BinaryIO | None, key_is_public: bool):
    if key is not None:
        key = (crypt.EdPubK.from_public_bytes(key.read()) if key_is_public
               else crypt.EdPrivK.from_private_bytes(key.read()).public_key())
    blueprint.verify(key)
    click.echo('Verification passed')
# crypt casc #
casccli = click.Group('casc', help='Secure public-key cascading')
cryptcli.add_command(casccli)
# crypt casc add-trust
@casccli.command()
@w_io
@click.argument('voucher', type=click.File('rb'))
@click.argument('vouchee', type=click.File('rb'))
@click.option('--vouchee-is-public', help='Treat the vouchee key as a public key, not a private key (useful if you are adding someone else\'s key)', is_flag=True, default=False)
@click.option('--overwrite', help='Allows overwriting an existing trust', is_flag=True, default=False)
def add_trust(blueprint: Blueprint, *, voucher: typing.BinaryIO, vouchee: typing.BinaryIO, vouchee_is_public: bool, overwrite: bool) -> Blueprint:
    crypt.cascade.add(blueprint.crypt.cascade, crypt.EdPrivK.from_private_bytes(voucher.read()),
                      crypt.EdPubK.from_public_bytes(vouchee.read()) if vouchee_is_public
                      else crypt.EdPrivK.from_private_bytes(vouchee.read()).public_key(), overwrite=overwrite)
    return blueprint

# Main
if __name__ == '__main__': cli()
