#!/bin/python3

#> Imports
#</Imports

#> Header >/
__all__ = ['ManifestException',]
class ManifestException(Exception):
    '''Base class for manifest-related problems'''
    def __init_subclass__(cls):
        __all__.append(cls.__name__)
class CorruptedFileException(ManifestException):
    '''When a non-manifest file is attempted to be used as a manifest'''
class ManifestTypeError(ManifestException, TypeError):
    '''When a manifest has an incorrect type or contains a part that is of an incorrect type (see derived `PartTypeError`)'''
class PartError(ManifestException):
    '''Issues relating to a manifest's parts, such as missing or incorrect parts'''
class MissingPartError(PartError):
    '''When a manifest is missing a required part for an action'''
class PartTypeError(ManifestTypeError):
    '''When a manifest has a part, but it is of the wrong type or does not contain a necessary value'''

# Finalize __all__
__all__ = tuple(__all__)
del ManifestException.__init_subclass__
