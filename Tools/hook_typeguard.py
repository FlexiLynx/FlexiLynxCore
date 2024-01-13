#!/bin/python3

#> Imports
import os
import sys
import typeguard
from pathlib import Path
from importlib import util as iutil
#</Imports

# Get entrypoint
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None): p = Path(ep)
elif (p := Path('__entrypoint__.py')).exists(): pass
elif (p := Path('../__entrypoint__.py')).exists(): pass
else:
    raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py, maybe set FLEXILYNX_ENTRYPOINT in env?')
sys.path.append(p.parent.as_posix())
__entrypoint__ = iutil.spec_from_file_location('__entrypoint__', p.as_posix()) \
                     .loader.load_module()

#> Main >/
print('<TypeGuard Hook> Installing import hook')
typeguard.install_import_hook()
print('<TypeGuard Hook> Chainloading __entrypoint__.__init__()')
__entrypoint__.__init__()
print('<TypeGuard Hook> Chainloading __entrypoint__.__setup__()')
__entrypoint__.__setup__()
