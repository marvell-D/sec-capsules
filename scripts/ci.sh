#!/usr/bin/env bash
set -euo pipefail

python_bin=${PYTHON:-python3}

"$python_bin" -m compileall src benchmarks tests
"$python_bin" -m unittest discover -s tests -v
