#!/bin/python3

'''Tools for working with files and paths'''

#> Imports
from pathlib import Path
#</Imports

#> Header >/
__all__ = ('clean_pycache', 'clean_empty')

def clean_pycache(root: Path):
    '''
        Recursively unlinks compiled Python files (`.pyc`)
            and the containing `__pycache__` directories
    '''
    for pycd in root.glob('**/__pycache__'):
        for pycf in pycd.glob('*.pyc'): pycf.unlink()
        try: pycd.rmdir()
        except OSError: pass
def clean_empty(root: Path, include_root: bool = False):
    '''
        Recursively rmdirs empty directories,
            not including `root` unless `include_root`
    '''
    for rp,ds,fs in root.walk(top_down=False):
        if (not include_root) and (rp == root): continue
        if fs: continue
        if not any(map(Path.exists, map(rp.joinpath, ds))):
            rp.rmdir()
