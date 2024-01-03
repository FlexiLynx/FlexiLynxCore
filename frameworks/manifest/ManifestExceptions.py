#!/bin/python3

#> Imports
import typing
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as EdPubK
#</Imports

#> Header >/
# Regular manifest exceptions
class ManifestException(Exception):
    '''The base class for all manifest-related exceptions'''
    __slots__ = ()
class CorruptedFileError(ManifestException):
    '''A file could not be loaded as a Manifest instance'''
    __slots__ = ('file', 'data')
    def __init__(self, *args, file: str | Path = None, data: bytes | None = None, **kwargs):
        self.file = file
        self.data = data
        super().__init__(*args, **kwargs)
class MissingPackHeaderError(CorruptedFileError):
    '''A (supposedly) packed file could not be loaded as a Manifest instance because it was missing a header'''
    __slots__ = ()
## Bound manifest exceptions
class BoundManifestException(ManifestException):
    '''The base class for all manifest-related exceptions that are bound to a specific Manifest instance'''
    __slots__ = ('manifest',)
    def __init__(self, manifest: 'Manifest', *args, **kwargs):
        self.manifest = manifest
        super().__init__(*args, **kwargs)
class InvalidSignatureError(BoundManifestException):
    '''Signature failed verification'''
    __slots__ = ()
class PacksDisabledError(BoundManifestException):
    '''An attempt to utilize a pack was made on a Manifest instance that does not support packs'''
    __slots__ = ()
### Cascade exceptions
class CascadeError(BoundManifestException):
    '''The base class for all cascade-related exceptions'''
    __slots__ = ()
class CascadeOverrideError(CascadeError):
    '''An attempt was made to add a key that had already vouched for another key in the cascade'''
    __slots__ = ('overridden',)
    def __init__(self, manifest: 'Manifest', overriden: str, *args, **kwargs):
        self.overriden = overriden
        super().__init__(manifest, *args, **kwargs)
class EmptyCascadeError(CascadeError):
    '''An attempt was made to check a key against a nonexistent or blank cascade'''
    __slots__ = ()
class BrokenCascadeError(CascadeError):
    '''A cascade broke off at a non-target key'''
    __slots__ = ('branch',)
    def __init__(self, manifest: 'Manifest', branch: EdPubK, *args, **kwargs):
        self.branch = branch
        super().__init__(manifest, *args, **kwargs)
class InitBrokenCascadeError(BrokenCascadeError):
    '''A cascade broke off at the initial key'''
    __slots__ = ()
class CascadeSignatureError(CascadeError, InvalidSignatureError):
    '''Signature failed verification inside of a cascade'''
    __slots__ = ()
class CircularCascadeError(CascadeError):
    '''A cascade chased its own tail'''
    __slots__ = ()
### Insane manifest exceptions
class InsaneManifestError(BoundManifestException):
    '''The base class for all manifest-related exceptions that are raised by `executor.is_insane()`'''
    __slots__ = ()
class InsaneSignatureError(InsaneManifestError, InvalidSignatureError):
    '''Signature failed verification'''
    __slots__ = ()
class UnknownValueError(InsaneManifestError):
    '''Manifest speaks of an unknown value in any field'''
    __slots__ = ('unknown_value',)
    def __init__(self, manifest: 'Manifest', unknown_value: typing.Any, *args, **kwargs):
        self.unknown_value = unknown_value
        super().__init__(manifest, *args, **kwargs)
class UnknownTypeError(UnknownValueError):
    '''Manifest is of an unknown type'''
    __slots__ = ()
class UnknownHashAlgorithmError(UnknownValueError):
    '''Manifest speaks of an unknown hashing algorithm'''
    __slots__ = ()
class UnknownByteEncodingError(UnknownValueError):
    '''Manifest speaks of an unknown byte encoding'''
    __slots__ = ()
class OtherRelationsError(InsaneManifestError):
    '''"other"-type manifest has illegal relatedepends'''
    __slots__ = ()
class UnsupportedVersionError(InsaneManifestError):
    '''Manifest demands a higher version of Python'''
    __slots__ = ('version',)
    def __init__(self, manifest: 'Manifest', version: tuple[int, int, int], *args, **kwargs):
        self.verison = version
        super().__init__(manifest, *args, **kwargs)
class TimeTravelError(InsaneManifestError):
    '''Manifest tries to perform time-travel'''
    __slots__ = ('delta',)
    def __init__(self, manifest: 'Manifest', delta: int, *args, **kwargs):
        self.delta = delta
        super().__init__(manifest, *args, **kwargs)
### Double-bound manifest exceptions
class DoubleBoundManifestException(BoundManifestException):
    '''The base class for all manifest-related exceptions that are bound to two Manifest instances'''
    __slots__ = ('manifest_b',)
    def __init__(self, manifest: 'Manifest', manifest_b: 'Manifest', *args, **kwargs):
        self.manifest_b = manifest_b
        super().__init__(manifest, *args, **kwargs)
class CrossInvalidSignatureError(DoubleBoundManifestException, InvalidSignatureError):
    '''manifest_b failed manifest's signature verification'''

# __all__ #
__all__ = tuple(n for n in dir() if isinstance((c := globals()[n]), type) and issubclass(c, ManifestException))
