#!/bin/python3

'''
    This is a stub file that simply re-exposes `__entrypoint__`
        for the purposes of importing as a package/module
'''

#> Package >/
from . import __entrypoint__

__all__ = __entrypoint__.__all__

__dir__ = __entrypoint__.__dir__
__getattr__ = __entrypoint__.__getattribute__
