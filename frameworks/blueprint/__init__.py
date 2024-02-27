#!/bin/python3

'''FlexiLynx's `blueprint` framework'''

#> Package >/
__all__ = ('DEFAULT_HASH_ALGORITHM', 'Blueprint', 'BlueProtocol', 'BaseManagedPackage', 'Package', 'crypt', 'generate', 'parts')

DEFAULT_HASH_ALGORITHM = 'sha3_384' # reasonably secure and forward-proof, but not too long (60 chars in Base85)

from FlexiLynx.core import logger
logger = logger.getChild('BP')

from .blueprint import Blueprint, BlueProtocol
from .package import BaseManagedPackage, Package
from . import crypt
from . import parts
from . import generate
