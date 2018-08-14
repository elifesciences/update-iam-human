#!/bin/bash
set -e
source venv/bin/activate
python -m src.main $@
