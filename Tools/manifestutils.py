#!/bin/python3

#> Imports
import os
import sys
import click
import importlib
import base64
import shlex
import typing
from io import SEEK_SET
from pathlib import Path
from importlib import util as iutil
from functools import partial, wraps
from hashlib import algorithms_guaranteed
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK, Ed25519PublicKey as EdPubK
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
from FlexiLynx.core.frameworks.manifest import *

# Define input/output formats
def auto_format(f: typing.BinaryIO) -> str:
    if (f.fileno() in {sys.stdout.buffer.fileno(), sys.stdin.buffer.fileno()}
        or ('.' not in f.name)): return 'ini'
    suff = f.name.rsplit('.', 1)[1].lower()
    if suff in {'ini', 'json', 'pack'}: return suff
    if suff == 'pakd': return 'pack'
    raise ValueError(f'Cannot automatically determine format of {f.name} (suff: {suff!r})')
def h_output(out: typing.BinaryIO, man: Manifest, fmt: typing.Literal['auto', 'ini', 'json', 'pack']):
    if not man.verify():
        click.echo('The manifest is dirty, signing it is recommended')
    click.echo(f'\nWrote {out.write({"ini": render_ini, "json": render_json, "pack": render_pack}[auto_format(out) if fmt == "auto" else fmt](man))} byte(s) to {out.name}', file=sys.stderr)
def h_input(inp: typing.BinaryIO, fmt: typing.Literal['auto', 'ini', 'json', 'pack']) -> Manifest:
    d = inp.read()
    click.echo(f'Read {len(d)} byte(s) from {inp.name}', file=sys.stderr)
    return {'ini': load_ini, 'json': load_json, 'pack': load_packed}[auto_format(inp) if fmt == 'auto' else fmt](d)

cw_format = click.option('--format', type=click.Choice(('auto', 'ini', 'json', 'pack')),
                         help='The format to use (defaults to auto)', default='auto')
def w_output(c):
    @click.option('--output', type=click.File('wb'), help=f'The file to write to (defaults to stdout)', default='-', show_default=False)
    @cw_format
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_output(*, output: typing.BinaryIO, format: typing.Literal['auto', 'ini', 'json', 'pack'], **kwargs):
        h_output(output, c(**kwargs), format)
    return c_w_output
def w_input(c):
    @click.argument('manifest', type=click.File('rb'))
    @cw_format
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_input(*, manifest: typing.BinaryIO, format: typing.Literal['auto', 'ini', 'json', 'pack'], **kwargs):
        c(manifest=h_input(manifest, format), **kwargs)
    return c_w_input
def w_io(c):
    @click.argument('manifest', type=click.File('r+b'))
    @click.option('--output', type=click.File('wb'), help=f'File to write to (defaults to overwriting MANIFEST; "-" for stdout)', default=None)
    @cw_format
    @wraps(c, assigned=('__name__', '__doc__', '__click_params__'))
    def c_w_io(*, manifest: typing.BinaryIO, output: typing.BinaryIO | None, format: typing.Literal['auto', 'ini', 'json', 'pack'], **kwargs):
        if (format == 'auto') and (output is None): format = auto_format(manifest) # force output format to match input format if output is stdout
        man = c(manifest=h_input(manifest, format), **kwargs)
        if output is None:
            if manifest.fileno() == sys.stdin.buffer.fileno():
                output = sys.stdin.buffer
            else:
                manifest.truncate(0)
                manifest.seek(0, SEEK_SET)
                output = manifest
        h_output(output, man, format)
    return c_w_io

# Misc. helpers
def w_carguments(*names: str) -> typing.Callable[[click.Command], click.Command]:
    def w_w_carguments(c: click.Command) -> click.Command:
        if not hasattr(c, '__click_params__'): c.__click_params__ = []
        c.__click_params__.extend(click.Argument((n,)) for n in reversed(names))
        return c
    return w_w_carguments
#</Header

#> Main >/
cli = click.Group(context_settings={'help_option_names': ('-h', '--help', '-?'), 'max_content_width': 160})

# Misc commands #
# Update
@cli.command()
@w_io
@click.option('-m', '--meta-version', help='Version-string that is meaningless to the parser', default=None)
@click.option('-r', '--default-root', type=click.Path(exists=True, file_okay=False, path_type=Path), help='Root path of content not in any pack', required=True)
@click.option('-I', '--include', help='Glob to add to includes (note that adding once removes defaults)', default=('**/*',), multiple=True)
@click.option('-E', '--exclude', help='Glob to add to excludes', default=('**/__pycache__/**/*', '**/MANIFEST*', '**/.git/**/*', '**/.gitignore'), multiple=True)
@click.option('-P', '--pack', type=(str, click.Path(exists=True, file_okay=False, path_type=Path)), help='Pack-name and root to add (adding this at least once enables packs)', default=None, multiple=True)
@click.option('-k', '--sign', type=click.File('rb'), help='Key to sign the manifest with')
@click.option('--store', help='Instead of updating the manifest, create a script that would update the manifest for usage later', is_flag=True, default=False)
def update(manifest: Manifest, *, meta_version: str | None,
           default_root: Path, include: tuple[str, ...], exclude: tuple[str, ...], pack: tuple[tuple[str, Path]],
           sign: typing.BinaryIO | None, store: bool) -> Manifest:
    '''
        Updates the MANIFEST's content (files)

        All given options for selecting files and packs are the same as "generate manifest"\n
        It is recommended to use --store to make a helper-script
    '''
    if store:
        click.echo(shlex.join((a for a in sys.argv if a != '--store')))
        raise click.exceptions.Exit()
    return generator.autoupdate_manifest(manifest, meta_version=meta_version,
                                         key=None if sign is None else EdPrivK.from_private_bytes(sign.read()), do_sign=sign is not None,
                                         files=generator.FilePack(root=default_root, include_glob=include, exclude_glob=exclude),
                                         packs={n: generator.FilePack(root=r, include_glob=include, exclude_glob=exclude) for n,r in pack})
# Sanity check
@cli.command()
@w_input
@click.option('--unsupported-version-fail', help='Fail when using an unsupported version of Python', is_flag=True, default=False)
def sanity_check(manifest: Manifest, *, unsupported_version_fail: bool):
    '''Checks a manifest for several defects / inconsistencies'''
    executor.is_insane(manifest, unsupported_version_fail)
# Inspect/info
@cli.command()
@w_input
def info(manifest: Manifest):
    '''Prints out information on MANIFEST'''
    click.echo(executor.render_info(manifest, 'verbose'))
# Transpose
@cli.command()
@click.argument('manifest', type=click.File('rb'))
@click.argument('new_format', type=click.Choice(('auto', 'ini', 'json', 'pack')))
@click.option('--output', type=click.File('wb'), help=f'The file to write to (defaults to stdout)', default='-', show_default=False)
@click.option('--input-format', type=click.Choice(('auto', 'ini', 'json', 'pack')),
              help='The format to use when reading MANIFEST (defaults to auto)', default='auto')
def transpose(*, manifest: typing.BinaryIO, input_format: str, new_format: str, output: typing.BinaryIO):
    '''Transposes MANIFEST to NEW_FORMAT'''
    return h_output(output, h_input(manifest, input_format), new_format)

# Generate #
generate_cli = click.Group('generate', help='Generate manifests and keys')
cli.add_command(generate_cli)
# Generate manifest
@generate_cli.command()
@w_output
@w_carguments('id', 'name', 'by', 'manifest_upstream', 'file_upstream')
@click.option('-t', '--type', 'type_', type=click.Choice(('other', 'plugin', 'module')), help='Type of manifest', default='other')
@click.option('-k', '--sign', type=click.File('rb'), help='Key to sign the manifest with')
@click.option('-d', '--desc', help='Description')
@click.option('-c', '--contact', help='Contact information of the creator')
@click.option('-r', '--default-root', type=click.Path(exists=True, file_okay=False, path_type=Path), help='Root path of content not in any pack', required=True)
@click.option('-I', '--include', help='Glob to add to includes (note that adding once removes defaults)', default=('**/*',), multiple=True)
@click.option('-E', '--exclude', help='Glob to add to excludes', default=('**/__pycache__/**/*', '**/MANIFEST*', '**/.git/**/*', '**/.gitignore'), multiple=True)
@click.option('-P', '--pack', type=(str, click.Path(exists=True, file_okay=False, path_type=Path)), help='Pack-name and root to add (adding this at least once enables packs)', default=None, multiple=True)
@click.option('--min-version', type=(int, int, int), metavar='<INT INT INT>', help='Enforce a minimum Python version (defaults to the current version)', default=sys.version_info[:3])
@click.option('--no-minimum-version', help='Do not enforce a minimum Python version', is_flag=True, default=False)
@click.option('--meta-version', help='Version-string that is meaningless to the parser', default=None)
@click.option('-B', '--before', help='Manifest ID that should load after this manifest', multiple=True)
@click.option('-A', '--after', help='Manifest ID that should load before this manifest', multiple=True)
@click.option('-R', '--requires', help='Manifest ID that must exist in order to load this manifest', multiple=True)
@click.option('-a', '--hash-algorithm', metavar='<NAME>', type=click.Choice(set.union({'list',}, algorithms_guaranteed)), help='Hashing algorithm for content (use -h list for a list)', default='sha1')
@click.option('--byte-encoding', type=click.Choice(set(filter(len, (e.removesuffix('decode') for e in getattr(base64, '__all__', dir(base64)) if e.endswith('decode'))))), help='Encoding for bytes as strings', default='b85')
def manifest(sign: typing.BinaryIO | None,
             default_root: Path, include: tuple[str, ...], exclude: tuple[str, ...], pack: tuple[tuple[str, Path]],
             no_minimum_version: bool, min_version: tuple[int, int, int],
             hash_algorithm: typing.Literal['list'] | str, **kwargs) -> Manifest:
    '''
        Generates a manifest

        ID and NAME correspond to the unique identifier of the manifest, and its display name\n
        BY is the name (or any identifier) of the manifest's creator\n
        MANIFEST_UPSTREAM and FILE_UPSTREAM correspond to where manifest updates and content updates are fetched from
    '''
    if hash_algorithm == 'list':
        click.echo('\n'.join(sorted(algorithms_guaranteed)))
        raise click.exceptions.Exit
    man = generator.autogen_manifest(**kwargs,
                                     key=None if sign is None else EdPrivK.from_private_bytes(sign.read()), do_sign=sign is not None,
                                     files=generator.FilePack(root=default_root, include_glob=include, exclude_glob=exclude),
                                     packs={n: generator.FilePack(root=r, include_glob=include, exclude_glob=exclude) for n,r in pack},
                                     min_python_version=None if no_minimum_version else min_version)
    return man
# Generate key
@generate_cli.command()
@click.argument('output', type=click.File('wb'), required=True)
def key(*, output: typing.BinaryIO):
    '''
        Generates an Ed25519 key suitible for signing manifests

        OUTPUT is the file to write output to, defaulting to "key.pyk" (use "-" to write to stdout)
    '''
    click.echo(f'\nWrote {output.write(EdPrivK.generate().private_bytes_raw())} byte(s) to {output.name}', file=sys.stderr)

# Crypt #
crypt_cli = click.Group('crypt', help='Sign and verify')
cli.add_command(crypt_cli)
# Generate key
crypt_cli.add_command(key, 'genkey')
# Sign manifest
@crypt_cli.command()
@w_io
@click.argument('key', type=click.File('rb'))
def sign(manifest: Manifest, *, key: typing.BinaryIO) -> Manifest:
    '''
        Signs a manifest with a given key

        KEY is the key to sign the manifest with\n
        MANIFEST is the manifest to sign, and to overwrite if --output is not given
    '''
    manifest.sign(EdPrivK.from_private_bytes(key.read()))
    return manifest
# Verify manifest
@w_input
@crypt_cli.command()
def verify(manifest: Manifest):
    '''Verifies MANIFEST's signature with its public-key'''
    if not manifest.verify():
        click.echo('Verification failed', file=sys.stderr)
        raise click.exceptions.Exit(1)
    click.echo('Verification succeeded', file=sys.stderr)

# Cascade commands #
cascade_cli = click.Group('cascade', help='Cascade public keys to add trust')
cli.add_command(cascade_cli)
# Add cascade
@cascade_cli.command()
@w_io
@click.argument('old', type=click.File('rb'))
@click.argument('new', type=click.File('rb'))
@click.option('--overwrite', help='Forcefully overwrite an existing remap', is_flag=True, default=False)
@click.option('--new-is-public', help='Treat NEW as a public key instead of as a private key', is_flag=True, default=False)
def remap(manifest: Manifest, *, old: typing.BinaryIO, new: typing.BinaryIO, overwrite: bool, new_is_public: bool) -> Manifest:
    manifest.remap(EdPrivK.from_private_bytes(old.read()),
                   EdPubK.from_public_bytes(new.read()) if new_is_public
                   else EdPrivK.from_private_bytes(new.read()).public_key(), overwrite)
    return manifest
# Check cascade
@cascade_cli.command()
@w_input
@click.argument('target', type=click.File('rb'))
@click.argument('against', type=click.File('rb'), default=None, required=False)
@click.option('--target-is-public', help='Treat TARGET as a public key instead of as a private key', is_flag=True, default=False)
@click.option('--against-is-public', help='Treat AGAINST as a public key instead of as a private key', is_flag=True, default=False)
@click.option('--exit-codes', help='Exit with error codes (CASC_ in Manifest class) instead of exceptions', is_flag=True, default=False)
def check(manifest: Manifest, *, target: typing.BinaryIO, against: typing.BinaryIO | None, target_is_public: bool, against_is_public: bool, exit_codes: bool):
    '''
        Checks if the TARGET key is valid through MANIFEST's remap cascade

        AGAINST is a key to check against--when not supplied, the manifest's public key is used
    '''
    def _deb(type: str, values: tuple[bytes, ...]):
        print({
            'check': '{} -?-> {}',
            'saw': 'Saw key: {}',
            'match': 'Matched target key: {}',
            'found': 'Found new key {}',
            'verify': 'Verified new key {2} using old key {0}',
        }[type].format(*(base64.b85encode(v).decode() for v in values)), file=sys.stderr)
    n = manifest.chk_cascade(
        EdPubK.from_public_bytes(target.read()) if target_is_public else EdPrivK.from_private_bytes(target.read()).public_key(),
        None if against is None
            else (EdPubK.from_public_bytes(against.read()) if against_is_public else EdPrivK.from_private_bytes(against.read()).public_key()),
        no_fail=exit_codes, debug_callback=_deb)
    if not exit_codes: return
    click.echo(f'Encountered exit code {n} = { {v: k for k,v in Manifest.__dict__.items() if k.startswith("CASC_")}[n]}', file=sys.stderr)
    raise click.exceptions.Exit(n)
# Map cascade
@cascade_cli.command('map')
@w_input
@click.option('--print-values', help='Print full values instead of indexes', is_flag=True, default=False)
@click.option('--complexity', type=int, help='How many chain-check iterations to run (defaults to amount of keys)', default=None)
def map_(manifest: Manifest, *, print_values: bool, complexity: int | None):
    click.echo('Flattening cascade...', file=sys.stderr)
    flat_cascade = []
    for pkey,(nkey,_) in manifest.crypt.key_remap_cascade.items():
        if pkey not in flat_cascade: flat_cascade.append(pkey)
        if nkey not in flat_cascade: flat_cascade.append(nkey)
    click.echo('Building chains...', file=sys.stderr)
    chains = []
    for _ in range(len(flat_cascade) if complexity is None else complexity):
        for pkey,(nkey,_) in manifest.crypt.key_remap_cascade.items():
            chained = False
            for chain in chains:
                if pkey not in chain: continue
                if nkey not in chain:
                    assert chain.index(pkey) == len(chain)-1
                    chain.append(nkey)
                    chained = True
            else:
                if not chained: chains.append([pkey, nkey])
    click.echo('Deduplicating chains...', file=sys.stderr)
    chains = {tuple(chain) for chain in filter(len, chains)}
    click.echo('Merging chains...', file=sys.stderr)
    schains = sorted(chains, key=lambda c: (c[0], len(c)))
    seen_chains = set()
    chains = ((seen_chains.add(c[0]), c)[1] for c in schains if c[0] not in seen_chains)
    def render(k: bytes) -> str: return manifest.crypt._encode_(k) if print_values else flat_cascade.index(k)
    click.echo('Keys:')
    for k in flat_cascade: click.echo(f'- {flat_cascade.index(k)}: {manifest.crypt._encode_(k)}')
    for nchain,chain in enumerate(chains):
        click.echo(f'Chain {nchain}:\n / {" ~> ".join(str(render(key)) for key in chain)} /')
# Main #
cli()
