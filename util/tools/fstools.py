#!/bin/python3

'''Tools for working with files and paths'''

#> Imports
from pathlib import Path
#</Imports

#> Header >/
__all__ = ('clean_pycache',)

def clean_pycache(root: Path):
    '''
        Recursively unlinks compiled Python files (`.pyc`)
            and the containing `__pycache__` directories
    '''
    for pycd in root.glob('**/__pycache__'):
        for pycf in pycd.glob('*.pyc'): pycf.unlink()
        try: pycd.rmdir()
        except OSError: pass
