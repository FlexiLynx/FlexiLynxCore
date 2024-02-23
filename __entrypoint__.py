#!/bin/python3

#> Imports
import sys
import typing
import tomllib
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
    # Import util
    util = _resolve_import('util')
    # Setup FlexiSpaces
    global FlexiLynx
    FlexiLynx = util.FlexiSpace('FlexiLynx', 'The shared library across FlexiLynx')
    (FlexiLynx@'core').util = util
    # Setup logger
    with open('logging.toml', 'rb') as f:
        FlexiLynx.core.util.logger.init(tomllib.load(f))
    FlexiLynx.logger = FlexiLynx.core.util.logger.root_logger
    FlexiLynx.core.logger = FlexiLynx.core.util.logger.core_logger
    # Add frameworks
    FlexiLynx.core@'frameworks'
    ## Add "blueprint" framework
    FlexiLynx.core.frameworks.blueprint = _resolve_import('frameworks.blueprint')
def __setup__():
    ...
#</Header

#> Main >/
# Testing code
def _test():
    print('_test() pre __init__()')
    global blueprint, corebp, corepkg, files, test_dualcascade, test_migrate, test_logger
    __init__()
    print('_test() after __init__()')
    from pathlib import Path
    from FlexiLynx.core.frameworks import blueprint
    corebp = blueprint.Blueprint.deserialize(Path('../Blueprints/flexilynx/core.json').read_text())
    print(corebp.serialize())
    prk = blueprint.crypt.EdPrivK.generate()
    puk = prk.public_key()
    corebp.sign(prk)
    print(corebp.serialize())
    with open('../shae.pyk', 'rb') as f:
        srk = blueprint.crypt.EdPrivK.from_private_bytes(f.read())
    blueprint.crypt.cascade.add(corebp.crypt.cascade, prk, srk.public_key())
    print(corebp.serialize())
    corepkg = blueprint.Package(corebp)
    match,mism,miss = corepkg.scan()
    print(f'--PRE  UPDATE--\nMatching: {", ".join(match)}\nMismatching: {", ".join(mism)}\nMissing: {", ".join(miss)}')
    #corepkg.update()
    match,mism,miss = corepkg.scan()
    print(f'--POST UPDATE--\nMatching: {", ".join(match)}\nMismatching: {", ".join(mism)}\nMissing: {", ".join(miss)}')

    #test = manifest.ContentManifest(
    #    'testid',
    #    0,
    #    manifest.parts.ContentManifestPart(
    #        upstream=None,
    #        files=manifest.parts.ContentManifestPart.Files(),
    #    ),
    #    manifest.parts.MetadataManifestPart(
    #        name='Test Manifest',
    #        desc=None,
    #        upstream=None,
    #        creator='Shae',
    #    ),
    #    manifest.parts.extended.KeyCascadePart(),
    #)
    def test_dualcascade():
        global kr_0, kr_1, keyspr, keyspb, badk, badkp, frm, to
        CTEST_BRK = True
        CTEST_ALT = True
        CTEST_FLP = True
        CTEST_CIR = True
        import random
        badk = manifest.crypt.EdPrivK.generate(); badkp = badk.public_key()
        for _ in range(1):
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
                info_callback=manifest.crypt._migrate_dualcascaderun_icallb)
    def test_migrate():
        import traceback
        global k0, k1, badkey, a, b
        k0 = blueprint.crypt.EdPrivK.generate()
        k1 = blueprint.crypt.EdPrivK.generate()
        badkey = blueprint.crypt.EdPrivK.generate()
        a = blueprint.Blueprint.deserialize_from_dict(corebp.serialize_to_dict())
        b = blueprint.Blueprint.deserialize_from_dict(corebp.serialize_to_dict())
        b.rel += 1
        print('Without signing (should fail)')
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key, b.crypt.cascade)
            a.verify()
        except: traceback.print_exc()
        print('Sign both with k0 (should succeed)')
        a.sign(k0)
        b.sign(k0)
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key, b.crypt.cascade)
            a.verify()
        except: traceback.print_exc()
        print('Sign b with k1 (should fail)')
        b.sign(k1)
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key)
            a.verify()
        except: traceback.print_exc()
        print('Cascade k0 to badkey in b (should fail)')
        blueprint.crypt.cascade.add(b.crypt.cascade, k0, badkey.public_key())
        b.sign(k1)
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key, b.crypt.cascade)
            a.verify()
        except: traceback.print_exc()
        print('Cascade k0 to k1 in b (should succeed)')
        blueprint.crypt.cascade.add(b.crypt.cascade, k0, k1.public_key(), overwrite=True)
        b.sign(k1)
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key, b.crypt.cascade)
            a.verify()
        except: traceback.print_exc()
        print('Cascade k0 to badkey in a (should succeed)')
        blueprint.crypt.cascade.add(a.crypt.cascade, k0, badkey.public_key())
        a.sign(k0)
        print(f'{a=}\n{b=}')
        try:
            a.verify()
            b.verify()
            a.migrate(b.crypt.key, b.crypt.cascade)
            a.verify()
        except: traceback.print_exc()
    test_migrate()
    def test_logger():
        FlexiLynx.logger.trace('test -1')
        FlexiLynx.logger.debug('test 0')
        FlexiLynx.logger.verbose('test 1')
        FlexiLynx.logger.info('test 2')
        FlexiLynx.logger.terse('test 2.5')
        FlexiLynx.logger.warning('test 3')
        FlexiLynx.logger.error('test 4')
        FlexiLynx.logger.critical('test 5')
        FlexiLynx.logger.fatal('test 6')
    test_logger()
if __name__ == '__main__': _test()
