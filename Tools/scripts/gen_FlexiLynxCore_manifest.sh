#!/bin/bash

${PYTHON:-} ./Tools/manifestutils.py gen manifest 'flexilynx.core' \
    'FlexiLynx Core' --desc 'Core files required to run FlexiLynx, including frameworks for manifests, modules, and plugins' \
    'Shae VanCleave' --contact 'https://github.com/Tiger-Tom' \
    'https://raw.githubusercontent.com/FlexiLynx/ManifestStore/main/flexilynx/core.ini' \
    'https://raw.githubusercontent.com/FlexiLynx/FlexiLynxCore/main/' \
    --default-root . --include '**/*.py' --exclude 'Tools/*' \
    --sign ../shae.pyk \
    --min-version 3 12 0 \
    --meta-version "commit $(git rev-parse --short HEAD)" \
    --output '../ManifestStore/flexilynx/core.ini'