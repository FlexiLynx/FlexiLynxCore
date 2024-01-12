#!/bin/python3

#> Imports
import sys
import typing
import logging
import importlib
from types import ModuleType
#</Imports

#> Header
MIN_PYTHON_VERSION = (3, 12, 0)
FlexiLynx = NotImplemented
def _resolve_import(modname: str, *, fn: typing.Callable = importlib.import_module):
    if not __package__:
        return fn(modname)
    return fn(f'.{modname}', package=__package__)
def __init__():
    '''Load core Python modules'''
    # Check for minimum version
    assert sys.version_info[:3] >= MIN_PYTHON_VERSION, f'Minimum Python version not met! Need {".".join(map(str, MIN_PYTHON_VERSION))}, got {".".join(map(str, sys.version_info[:3]))}'
    # Setup FlexiSpaces #
    global FlexiLynx
    flexispacelib = _resolve_import('libraries.flexispacelib')
    # Base namespace
    FlexiLynx = flexispacelib.TFlexiSpace('FlexiLynx', 'The shared library across FlexiLynx', assimilate=True)
    ## Core namespace
    _core = FlexiLynx/'core'
    ### Add env-config library
    _core.envconfiglib = _resolve_import('libraries.envconfiglib')
    ### Setup logger
    FlexiLynx.core.loglib = _resolve_import('libraries.loglib')
    FlexiLynx.logger = FlexiLynx.core.loglib.mklogger()
    ### Add other libraries
    _core.encodings = _resolve_import('libraries.encodings')
    _core.ffetch = _resolve_import('libraries.ffetch', fn=flexispacelib.LazyFSModule)
    _core.flexispacelib = flexispacelib
    _core.packlib = _resolve_import('libraries.packlib', fn=flexispacelib.LazyFSModule)
    _core.util = _resolve_import('libraries.util')
    ### Add framewarks
    _core/'frameworks'
    #### "manifest" framework
    _core.frameworks.manifest = _resolve_import('frameworks.manifest_new')
def __setup__():
    ...
#</Header

#> Main >/
# Testing code
if __name__ == '__main__':
    __init__()
    from FlexiLynx.core.frameworks import manifest
    test = manifest.base.ManifestType('test', idp=manifest.parts.IDManifestPart)
    testi = test('outerid', -1, idp=manifest.parts.IDManifestPart('innerid', 32767))
    from FlexiLynx.core.frameworks.manifest import crypt
    from FlexiLynx.core.frameworks.manifest.crypt import cascade
    from FlexiLynx.core.frameworks.manifest.parts import extended
    k0 = crypt.EdPrivK.generate()
    k1 = crypt.EdPrivK.generate()
    k2 = crypt.EdPrivK.generate()
    k3 = crypt.EdPrivK.generate()
    k4 = crypt.EdPrivK.generate()
    k5 = crypt.EdPrivK.generate()
    test2 = manifest.base.ManifestType('test2', cascade=extended.KeyCascadePart)
    test2i = test2('test2id', 0, None)
    crypt.sign(test2i, k0)
    cascade.add_key(test2i, k0, k1.public_key())
    cascade.add_key(test2i, k1, k2.public_key())
    cascade.add_key(test2i, k2, k3.public_key())
    cascade.add_key(test2i, k3, k4.public_key())
    cascade.add_key(test2i, k4, k5.public_key())
    cascade.add_key(test2i, k5, k0.public_key())

    def test_logger():
        FlexiLynx.logger.debug('test 0')
        FlexiLynx.logger.verbose('test 1')
        FlexiLynx.logger.info('test 2')
        FlexiLynx.logger.warning('test 3')
        FlexiLynx.logger.error('test 4')
        FlexiLynx.logger.critical('test 5')
        FlexiLynx.logger.irrec('test 6')
    test_logger()
