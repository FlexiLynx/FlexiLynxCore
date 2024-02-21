#!/bin/bash

BP=`cat ../Blueprints/flexilynx/core.json | ./Tools/scripts/updblueprint.sh`
echo "$BP" > ../Blueprints/flexilynx/core.json #\
    #&& (cd ../Blueprints/; git add flexilynx/core.json && git commit -m 'Automatically updated from commit in FlexiLynxCore' && git push)