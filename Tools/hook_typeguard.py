#!/bin/python3

#> Imports
import os
import sys
import typeguard
from pathlib import Path
from importlib import util as iutil
#</Imports

# Find entrypoint
if ep := os.getenv('FLEXILYNX_ENTRYPOINT', None): p = Path(ep)
elif (p := Path('__entrypoint__.py')).exists(): pass
elif (p := Path('../__entrypoint__.py')).exists(): pass
else:
    raise FileNotFoundError('Could not find __entrypoint__.py or ../__entrypoint__.py, maybe set FLEXILYNX_ENTRYPOINT in env?')
sys.path.append(p.parent.as_posix())

# Caching prevents TypeGuard instrumentation
sys.dont_write_bytecode = True
for f in p.parent.glob('**/__pycache__/*.pyc'):
    f.unlink()
    print(f'Unlinked cache: {f}')

# Load entrypoint
__entrypoint__ = iutil.spec_from_file_location('__entrypoint__', p.as_posix()) \
                     .loader.load_module()

#> Main >/
#typeguard.config.debug_instrumentation = True
class Finder(typeguard.TypeguardFinder):
    INCLUDE = ('util', 'frameworks', 'FlexiLynx')
    EXCLUDE = ()
    def should_instrument(self, module_name: str):
        if (not (any(module_name.startswith(i) for i in self.INCLUDE))
                or any(module_name.startswith(e) for e in self.EXCLUDE)):
            print(f'<TypeGuard Hook> Skipped {module_name!r}')
            return False
        print(f'<TypeGuard Hook> Check {module_name!r}')
        return True
print('<TypeGuard Hook> Installing import hook')
typeguard.install_import_hook(cls=Finder)
print('<TypeGuard Hook> Chainloading __entrypoint__.__load__()')
__entrypoint__.__load__()
print('<TypeGuard Hook> Chainloading __entrypoint__.__setup__()')
__entrypoint__.__setup__()
