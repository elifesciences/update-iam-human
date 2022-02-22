#!/bin/bash
# used to immediately rotate credentials of specific individuals.
# usage: ./update-iam-prompt.sh
#        ./update-iam-prompt.sh --execute
set -e
source venv/bin/activate
python -m src.cli --max-key-age=0 $@
