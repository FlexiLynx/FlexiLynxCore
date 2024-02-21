#!/bin/bash

python3.12 ./Tools/blueutils.py gen blueprint \
    'flexilynx.core' \
    -n 'FlexiLynx Core Package' \
    -d 'Core files required to run FlexiLynx' \
    -u 'https://raw.githubusercontent.com/FlexiLynx/Blueprints/main/flexilynx/core.json' \
    -U 'https://raw.githubusercontent.com/FlexiLynx/FlexiLynxCore/main/'
echo # add trailing newline