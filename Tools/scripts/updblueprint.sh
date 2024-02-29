#!/bin/bash

python3.12 ./Tools/blueutils.py add files - --root . \
    __entrypoint__.py \
    util/*.py util/singleton/*.py util/tools/*.py \
    frameworks/blueprint/*.py \
    frameworks/module/*.py
echo # add trailing newline