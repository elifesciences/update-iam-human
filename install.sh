#!/bin/bash
set -e # everything must succeed.
echo "[-] install.sh"

python=/usr/bin/python3.6
py=${python##*/} # ll: python3.5

# check for exact version of python3
if [ ! -e "venv/bin/$py" ]; then
    echo "could not find venv/bin/$py, recreating venv"
    rm -rf venv
    $python -m venv venv
fi

source venv/bin/activate

pip install -r requirements.txt --no-cache-dir

echo "[✓] install.sh"
