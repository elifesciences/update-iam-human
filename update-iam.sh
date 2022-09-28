#!/bin/bash
# used to rotate the credentials of a list of individuals.
# usage: GH_CREDENTIALS_FILE=/path/to/credentials ./update-iam.sh /path/to/humans.csv
#        GH_CREDENTIALS_FILE=/path/to/credentials ./update-iam.sh /path/to/humans.csv --execute
set -e

gh_credentials_file=$GH_CREDENTIALS_FILE

if [ -z "$GH_CREDENTIALS_FILE" ]; then
    echo "'GH_CREDENTIALS_FILE' is unset. This is the path to your github token."
    exit 1
fi

source venv/bin/activate
python -m src.main $@
