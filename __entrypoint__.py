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
def _resolve_import(modname: str):
    if not __package__:
        return importlib.import_module(modname)
    return importlib.import_module(f'.{modname}', package=__package__)
def __init__():
    '''Load core Python modules'''
    # Check for minimum version
    assert sys.version_info[:3] >= MIN_PYTHON_VERSION, f'Minimum Python version not met! Need {".".join(map(str, MIN_PYTHON_VERSION))}, got {".".join(map(str, sys.version_info[:3]))}'
    # Setup FlexiSpaces #
    global FlexiLynx
    flexispacelib = _resolve_import('flexispacelib')
    # Base namespace
    FlexiLynx = flexispacelib.TFlexiSpace('FlexiLynx', 'The shared library across FlexiLynx', assimilate=True)
    ## Core namespace
    _core = FlexiLynx/'core'
    ### Add env-config
    _core.envconfiglib = _resolve_import('envconfiglib')
    _core.EConf = _core.envconfiglib.EnvConfig('LYNXCONFIG', type_=str)
    ### Add packlib
    _core.packlib = _resolve_import('packlib')
    ### Add flexispacelib
    _core.TFlexiSpace = flexispacelib.TFlexiSpace
    ### Add manifestlib
    _core.manifestlib = _resolve_import('manifestlib')
    # Setup logger
    FlexiLynx.logger = _resolve_import('fllogger').mklogger()
def __setup__():
    ...
#</Header

#> Main >/
# Testing code
__init__()

_core = FlexiLynx.core
privkey = _core.manifestlib.ManifestCore.EdPrivK.generate()
man = _core.manifestlib.Manifest(
    id='testmod', real_version=0, type='module', format_version=1,
    upstream=_core.manifestlib.types.Manifest_upstream(manifest='Manifest.upstream.manifest val', files='Manifest.upstream.files val'),
    crypt=_core.manifestlib.types.Manifest_crypt(signature=None, public_key=privkey.public_key()),
    version=_core.manifestlib.types.Manifest_version(meta_version='Manifest.version.meta_version val', last_update_time=-1, last_update_time_pretty='lutp', first_creation_time=-2, first_creation_time_pretty='fctp'),
    metadata=_core.manifestlib.types.Manifest_metadata(name='Test Module', by='Shae'),
    relatedepends=_core.manifestlib.types.Manifest_relatedepends(python_implementation='cpython', platform='linux'),
    contentinfo=None,
    contentdata=_core.manifestlib.types.Manifest_contentdata(content_key_a=b'content_val_a', content_key_b=b'content_val_b'),
)
