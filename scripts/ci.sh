#!/usr/bin/env bash
set -euo pipefail

python -m compileall src tests
python -m unittest discover -s tests -v

