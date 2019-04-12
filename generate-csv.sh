#!/bin/bash
set -e
test -d venv || {
    echo "run install.sh first"
    exit 1
}
source venv/bin/activate
python -m src.generate_csv
