#!/bin/python3

#> Imports
#</Imports

#> Header >/
__all__ = ['ManifestException',]
class ManifestException(Exception):
    '''Base class for manifest-related problems'''
    def __init_subclass__(cls):
        __all__.append(cls.__name__)
class MissingPartError(ManifestException):
    '''When a manifest is missing a required part for an action'''

# Finalize __all__
__all__ = tuple(__all__)
del ManifestException.__init_subclass__
