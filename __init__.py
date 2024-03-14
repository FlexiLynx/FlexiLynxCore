#!/bin/python3

'''
    This is a stub file that simply re-exposes `__entrypoint__`
        for the purposes of importing as a package/module
'''

#> Package >/
from . import __entrypoint__
globals().update(__entrypoint__.__dict__)
