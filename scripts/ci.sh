#!/usr/bin/env bash
set -euo pipefail

python_bin=${PYTHON:-python3}

"$python_bin" -m compileall src tests
"$python_bin" -m unittest discover -s tests -v
