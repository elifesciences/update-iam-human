#!/bin/bash
set -e # everything must succeed.
echo "[-] install.sh"

. mkvenv.sh

source venv/bin/activate

if [ ! -e requirements.txt.lock ]; then
    # initial case
    pip install -r requirements.txt --no-cache-dir
    pip freeze > requirements.txt.lock
else
    # normal case
    pip install -r requirements.txt.lock
fi

echo "[✓] install.sh"
