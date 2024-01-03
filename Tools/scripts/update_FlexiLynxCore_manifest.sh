#!/bin/bash

${PYTHON:-} ./Tools/manifestutils.py mod update ../ManifestStore/flexilynx/core.ini \
    --default-root . --include '**/*.py' --exclude 'Tools/*' \
    --sign ../shae.pyk \
    --meta-version "commit $(git rev-parse --short HEAD)"