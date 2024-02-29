#!/bin/bash

python3.12 ./Tools/blueutils.py add files - --root . `git ls-tree -r main --name-only $(find . -name '*.py' -not -path './Tools/**' -not -name 'test.py')`
echo # add trailing newline