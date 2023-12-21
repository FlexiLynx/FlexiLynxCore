#!/bin/python3

#> Imports
import hashlib
import typing
from pathlib import Path

from .ManifestCore import Manifest
from .ManifestTypes import *
#</Imports

#> Header >/
def find_tree(root: Path, sort_func: typing.Callable[[Path], typing.Any] = lambda p: p.parts,
              include_glob: tuple[str, ...] = ('**/*',),
              exclude_glob: tuple[str, ...] = ('__pycache__/**', 'MANIFEST.*'),
              include_func: typing.Callable[[Path], typing.Any] = lambda p: p.is_file()) -> tuple[Path]:
    return sorted(
        sum((tuple(p.relative_to(root) for p in root.glob(ig)
                   if (not any(p.match(eg) for eg in exclude_glob)) and include_func(p))
             for ig in include_glob), start=()),
        key=sort_func,
    )
def hash_tree(tree: tuple[Path], algorithm: typing.Literal[*hashlib.algorithms_available], pack: str | None = None) -> Manifest_contentdata:
    return Manifest_contentdata({f.as_posix() if pack is None else f'{pack}@{f.as_posix()}':
                                 hashlib.new(algorithm, f.read_bytes()).digest() for f in tree})
