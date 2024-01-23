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
    _core.ffetch = _resolve_import('libraries.ffetch')
    _core.flexispacelib = flexispacelib
    _core.packlib = _resolve_import('libraries.packlib')
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
def _test():
    print('_test() pre __init__()')
    global manifest, test, test_dualcascade, test_migrate, test_logger
    __init__()
    print('_test() after __init__()')
    from FlexiLynx.core.frameworks import manifest
    test = manifest.ContentManifest(
        'testid',
        0,
        manifest.parts.ContentManifestPart(
            upstream=None,
            files=manifest.parts.ContentManifestPart.Files(),
        ),
        manifest.parts.MetadataManifestPart(
            name='Test Manifest',
            desc=None,
            upstream=None,
            creator='Shae',
        ),
        manifest.parts.extended.KeyCascadePart(),
    )
    def test_dualcascade():
        global kr_0, kr_1, keyspr, keyspb, badk, badkp, frm, to
        CTEST_BRK = True
        CTEST_ALT = True
        CTEST_FLP = True
        CTEST_CIR = True
        import random
        badk = manifest.crypt.EdPrivK.generate(); badkp = badk.public_key()
        for _ in range(1000):
            kr_0 = {}; kr_1 = {}
            keyspr = tuple(manifest.crypt.EdPrivK.from_private_bytes(k) for k in {manifest.crypt.EdPrivK.generate().private_bytes_raw() for _ in range(1000)})
            keyspb = tuple(k.public_key() for k in keyspr)
            for i in range(len(keyspr)-1):
                #print(f'{FlexiLynx.core.encodings.encode("b85", keyspb[i].public_bytes_raw())} trust {FlexiLynx.core.encodings.encode("b85", keyspb[i+1].public_bytes_raw())}')
                kr_0[keyspb[i].public_bytes_raw()] = manifest.crypt.cascade.create(keyspr[i], keyspb[i+1]) # correct path
                if CTEST_BRK and not random.randint(0, len(keyspr)*4):
                    print(f'Cascade broken off: {FlexiLynx.core.encodings.encode("b85", keyspb[i].public_bytes_raw())} -> (badkey){FlexiLynx.core.encodings.encode("b85", badkp.public_bytes_raw())}')
                    kr_0[keyspb[i].public_bytes_raw()] = manifest.crypt.cascade.create(keyspr[i], badkp)
                if CTEST_ALT and not random.randint(0, 1):
                    kr_1[keyspb[i].public_bytes_raw()] = manifest.crypt.cascade.create(keyspr[i], badkp) # incorrect path in the alternative route
                    kr_0,kr_1 = kr_1,kr_0
                elif CTEST_FLP and not random.randint(0, 1): kr_0,kr_1 = kr_1,kr_0
            if CTEST_CIR and random.randint(0, 1):
                print('Cascade is continuously circular unless broken in middle')
                kr_0[keyspb[-1].public_bytes_raw()] = manifest.crypt.cascade.create(keyspr[-1], keyspb[0])
            frm = keyspb[i := random.randint(0, len(keyspb)-1)]
            to = random.choice(keyspb[i:])
            print(f'Goal: ({i}){FlexiLynx.core.encodings.encode("b85", frm.public_bytes_raw())} -> {FlexiLynx.core.encodings.encode("b85", to.public_bytes_raw())}')
            manifest.crypt.cascade.dualrun(to, frm, kr_0, kr_1,
                info_callback=lambda l,s,d,a: False and print(f'{d} a,b={"b,a" if s else "a,b"} {l}: {", ".join(FlexiLynx.core.encodings.encode("b85", b) for b in a)}'))
    def test_migrate():
        import traceback
        global k0, k1, badkey, a, b
        k0 = manifest.crypt.EdPrivK.generate()
        k1 = manifest.crypt.EdPrivK.generate()
        badkey = manifest.crypt.EdPrivK.generate()
        a = test.m_import(test.m_export())
        b = test.m_import(test.m_export())
        b.rel += 1
        print('Without signing')
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
        print('Sign both with k0')
        manifest.crypt.sign(a, k0)
        manifest.crypt.sign(b, k0)
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
        print('Sign b with k1')
        manifest.crypt.sign(b, k1)
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
        print('Cascade k0 to badkey in b')
        manifest.crypt.cascade.add_key(b, k0, badkey.public_key())
        manifest.crypt.sign(b, k1)
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
        print('Cascade k0 to k1 in b')
        manifest.crypt.cascade.add_key(b, k0, k1.public_key(), overwrite_cascade=True)
        manifest.crypt.sign(b, k1)
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
        print('Cascade k0 to badkey in a')
        manifest.crypt.cascade.add_key(a, k0, badkey.public_key())
        manifest.crypt.sign(a, k0)
        print(f'{a=}\n{b=}')
        try: manifest.crypt.migrate(b, a)
        except: traceback.print_exc()
    def test_logger():
        FlexiLynx.logger.debug('test 0')
        FlexiLynx.logger.verbose('test 1')
        FlexiLynx.logger.info('test 2')
        FlexiLynx.logger.warning('test 3')
        FlexiLynx.logger.error('test 4')
        FlexiLynx.logger.critical('test 5')
        FlexiLynx.logger.irrec('test 6')
    test_logger()
if __name__ == '__main__': _test()
