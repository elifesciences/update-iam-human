#!/bin/bash
# used to *immediately* rotate the credentials of a specific individual.
# usage: GH_CREDENTIALS_FILE=/path/to/credentials ./update-iam-prompt.sh
#        GH_CREDENTIALS_FILE=/path/to/credentials ./update-iam-prompt.sh --execute
set -e

if [ -z "$GH_CREDENTIALS_FILE" ]; then
    echo "'GH_CREDENTIALS_FILE' is unset. This is the path to your github token."
    exit 1
fi

source venv/bin/activate
python -m src.cli --max-key-age=0 $@
