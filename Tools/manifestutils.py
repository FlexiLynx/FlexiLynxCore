#!/bin/python3

#> Imports
import os
import sys
import io
import click
import importlib
import base64
import typing
from pathlib import Path
from hashlib import algorithms_guaranteed
from importlib import util as iutil
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as EdPrivK
#</Imports

# Get entrypoint
sys.path.pop(0); sys.path.insert(0, '.')
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None):
    _spec = iutil.spec_from_file_location('__entrypoint__', ep)
else:
    if not Path('__entrypoint__.py').exists():
        if Path('../__entrypoint__.py').exists(): os.chdir('..')
        else:
            raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py')
    _spec = iutil.spec_from_file_location('__entrypoint__', './__entrypoint__.py')
__entrypoint__ = iutil.module_from_spec(_spec)
_spec.loader.exec_module(__entrypoint__)

#> Header >/
__entrypoint__.__init__()
from FlexiLynx.core import manifestlib

# Repeated constants
OUTPUT_FORMATS = {
    'ini': manifestlib.render_ini,
    'json': manifestlib.render_json,
    'packed': manifestlib.render_pack,
    'dict': lambda m: repr(m.as_dict()).encode(),
    'repr': lambda m: repr(m).encode(),
}



cli = click.Group()

# Create
@cli.command()
## Arguments
@click.argument('id')
@click.argument('name')
@click.argument('by')
## Creator info
@click.option('-d', '--desc', help='Optional description of the manifest\'s contents/purpose', default=None)
@click.option('-c', '--contact', help='Optional contact information for the creator', default=None)
## Type
@click.option('-t', '--type', 'type_', type=click.Choice(('other', 'plugin', 'module')), help='The type of the manifest ("other" by default)', default='other')
## Cryptography
@click.option('-k', '--key', type=click.Path(exists=True, dir_okay=False, path_type=Path), help='The key to sign the manifest with', default=(p if (p := Path('key.pyk')).exists() else None), required=not p.exists())
@click.option('-h', '--hash-algorithm', type=click.Choice(algorithms_guaranteed), help='The hashing algorithm to use', default='sha1')
@click.option('--byte-encoding', type=click.Choice(set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode')), help='The encoding for bytes', default='b85')
## Upstreams
@click.option('-mup', '--manifest-upstream', help='The URL to fetch manifest updates from', required=True)
@click.option('-fup', '--file-upstream', help='The URL to fetch content updates from', required=True)
## Versioning
@click.option('--meta-version', help='The optional "meta-version" (meaningless to the parser) to embed in the manifest', default=None)
@click.option('--min-python-version', type=int, nargs=3, help='The minumum version of Python to allow (defaults to the current version)', default=sys.version_info[:3])
@click.option('--no-minimum-version', help='Enforce no minimum Python version', is_flag=True, default=False)
## Content
@click.option('-r', '--default-root', type=click.Path(exists=True, file_okay=False, path_type=Path), help='The root for the default (non-pack) content list', required=True)
@click.option('--include', help='A glob to include (defaults to "*/**")', default=('**/*',), multiple=True)
@click.option('--exclude', help='A glob to exclude (defaults to "__pycache__/**" and "MANIFEST*")', default=('__pycache__/**', 'MANIFEST*'), multiple=True)
@click.option('--pack', type=(str, Path), help='A pack and root to add. Adding this once enables packs. Given in "name" "root-path" form) form', multiple=True)
## Relation
@click.option('-B', '--before', help='A manifest ID that should be loaded (if it exists) after this one', multiple=True)
@click.option('-A', '--after', help='A manifest ID that should be loaded (if it exists) before this one', multiple=True)
@click.option('-R', '--requires', help='A manifest ID that needs to exist, otherwise this manifest will not load', multiple=True)
## Output
@click.option('--output', type=click.File('wb'), help='The file to write to (defaults to stdout)', default='-')
@click.option('--format', type=click.Choice(OUTPUT_FORMATS.keys()), help='The format to write as', default='ini')

def create(*, id: str, name: str, by: str,
           desc: str, contact: str | None,
           type_: typing.Literal['other', 'plugin', 'module'],
           key: Path, hash_algorithm: typing.Literal[*algorithms_guaranteed], byte_encoding: typing.Literal[*set(e.removesuffix('decode') for e in dir(base64) if e.endswith('decode') and e != 'decode')],
           manifest_upstream: str, file_upstream: str,
           meta_version: str | None, min_python_version: tuple[int, int, int] | None, no_minimum_version: bool,
           default_root: Path, include: tuple[str, ...], exclude: tuple[str, ...], pack: tuple[tuple[str, Path], ...],
           before: tuple[str, ...], after: tuple[str, ...], requires: tuple[str, ...],
           output: io.BytesIO, format: typing.Literal[*OUTPUT_FORMATS.keys()]):
    '''
        Creates a new Manifest

        ID is the unique ID of this manifest-package\n
        NAME is the name of the manifest-package, independent from the ID
        BY is the name of the creator
    '''
    man = manifestlib.generator.autogen_manifest(
        id=id, type_=type_,
        name=name, by=by, desc=desc, contact=contact,
        key=key,
        files=manifestlib.generator.FilePack(root=default_root, include_glob=include, exclude_glob=exclude),
            packs={n: manifestlib.generator.FilePack(root=r, include_glob=include, exclude_glob=exclude) for p,r in pack},
        manifest_upstream=manifest_upstream, file_upstream=file_upstream,
        hash_algorithm=hash_algorithm,
        byte_encoding=byte_encoding,
        meta_version=meta_version,
        min_python_version=None if no_minimum_version else min_python_version,
        before=before, after=after, requires=requires,
    )
    output.write(OUTPUT_FORMATS[format](man))

# Update
@cli.command()
def update(): pass

# Modify
@cli.command()
def modify(): pass

# Cascade
@cli.command()
def cascade(): pass

# Genkey
@cli.command()
@click.argument('output', type=click.File('wb'), default='key.pyk')
def genkey(*, output: io.BytesIO):
    '''
        Generates an Ed25519 key suitible for signing manifests

        OUTPUT is the file to write output to, defaulting to "key.pyk" (use "-" to write to STDOUT)
    '''
    output.write(EdPrivK.generate().private_bytes_raw())


cli()
