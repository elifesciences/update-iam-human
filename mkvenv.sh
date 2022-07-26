#!/bin/bash
set -e

# update_iam_human requires Python 3.6+ with *dictionaries maintaining insertion order*
python=''
pybinlist=("python3.8" "python3") # use ascending order.

for pybin in ${pybinlist[*]}; do
    hash "$pybin" || continue
    python=$pybin
    break
done

if [ -z "$python" ]; then
    echo "no usable python found, exiting"
    exit 1
fi

if [ ! -e "venv/bin/$python" ]; then
    echo "could not find venv/bin/$python, recreating venv"
    rm -rf venv
    $python -m venv venv
else
    echo "using $python"
fi
