#!/bin/bash

# when will Arch update core/Python?
PYTHON=python3.12 ./Tools/scripts/update_FlexiLynxCore_manifest.sh \
    && (cd ../ManifestStore; git add FlexiLynx/Core.manifest.ini && git commit -m 'Automatically updated from commit in FlexiLynxCore' && git push)