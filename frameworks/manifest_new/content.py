#!/bin/python3

#> Imports
import typing
import hashlib
from pathlib import Path

from .base import logger
#</Imports

#> Header >/
__all__ = ('hash_tree', 'FileDiff')

def hash_tree(base: Path, *, hash_method: str | typing.Callable[[bytes], bytes] = 'sha256',
              glob: str = '**/*', qual: typing.Callable[[Path], bool] = lambda p: p.suffix != '.pyc') -> typing.Iterator[tuple[Path, bytes]]:
    '''
        Hashes an entire directory of files (found with `glob` and filtered by `qual`) using `hash_method`
            The default value of `qual` excludes `.pyc` files
    '''
    h = (lambda b: hashlib.new(hash_method, b).digest()) if isinstance(hash_method, str) else hash_method
    return ((p,h(p.read_bytes())) for p in base.glob(glob) if p.is_file() and qual(p))

class FileDiff(typing.NamedTuple):
    '''Shows the differences between two sets of files (see `generate()`)'''
    removed: tuple[Path, ...]
    added:   tuple[Path, ...]
    changed: tuple[Path, ...]
    same:    tuple[Path, ...]

    @classmethod
    def diff(cls, local: dict[Path, bytes], new: dict[Path, bytes]) -> typing.Self:
        '''Generates a new FileDiff from two dicts of files and hashes'''
        changed = tuple(p for p in (local.keys() & new.keys()) if local[p] != new[p])
        return cls(removed=tuple(local.keys()-new.keys()),
                   added=tuple(new.keys()-local.keys()),
                   changed=changed, same=tuple((local.keys() & new.keys()) - frozenset(changed)))
    @classmethod
    def generate(cls, base: Path, target: dict[Path, bytes], **htree_kwargs) -> typing.Self:
        '''
            Generates a new FileDiff from `target`, a dict of files and hashes, and a `base` path searched with `hash_tree()`
                Keyword arguments (`htree_kwargs`) are passed to `hash_tree()`, see `help(hash_tree())`
        '''
        return cls.diff(dict(hash_tree(base, **htree_kwargs)), target)

    def render(self, base: Path, files: dict[Path, bytes], *, do_uninstall: bool = False,
               hash_method: str | typing.Callable[[bytes], bytes] = 'sha256', **diff_htree_args) -> typing.Self:
        '''Installs changed files from `files` and then generates a new `FileDiff` from `base`'''
        h = (lambda b: hashlib.new(hash_method, b).digest()) if isinstance(hash_method, str) else hash_method
        logger.info(f'Installing up to {min(len(files), len(removed)+len(added)+len(changed))} file(s)')
        for p,c in (files.keys() - frozenset(self.same)):
            logger.verbose(f'Writing {len(c)} byte(s) to {p}')
            logger.debug(f'Wrote {p.write_bytes(c)} byte(s) to {p}')
        if do_uninstall and self.removed:
            logger.info(f'Uninstalling {len(self.removed)} file(s)')
            for p in self.removed: p.unlink()
        # note: whilst passing in `h` to `hash_tree()` instead of `hash_method` may reduce the need for a lambda construction,
        #  it may not be equivelant to passing `hash_method` to `hash_tree()` directly if `hash_tree()` has been overriden
        # in summary, `hash_method` is passed as given so that `render(base, files, **kwargs)` returns the same as `hash_tree(base, **kwargs)`
        return self.generate(base, {p: h(c) for p,c in files.items()}, hash_method=hash_method, **diff_htree_args)
