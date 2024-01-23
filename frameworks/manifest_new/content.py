#!/bin/python3

#> Imports
import typing
import hashlib
from pathlib import Path
#</Imports

#> Header >/
__all__ = ('hash_tree',)

def hash_tree(base: Path, *, hash_method: str | typing.Callable[[bytes], bytes] = 'sha256',
              glob: str = '**/*', qual: typing.Callable[[Path], bool] = lambda p: p.suffix != '.pyc') -> typing.Iterator[tuple[Path, bytes]]:
    '''
        Hashes an entire directory of files (found with `glob` and filtered by `qual`) using `hash_method`
            The default value of `qual` excludes `.pyc` files
    '''
    h = (lambda b: hashlib.new(hash_method, b).digest()) if isinstance(hash_method, str) else hash_method
    return ((p,h(p.read_bytes())) for p in base.glob(glob) if p.is_file() and qual(p))
