#!/bin/bash
set -e

# update_iam_human requires 3.6+ , *depends on dict maintaining order*
python=''
pybinlist=("python3.6", "python3.7") # use ascending order.

for pybin in ${pybinlist[*]}; do
    which "$pybin" &> /dev/null || continue
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
