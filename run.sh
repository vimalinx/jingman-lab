#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Reuse only the verified runtime versions; otherwise install an isolated venv.
compatible() {
  "$1" -c 'import sys, importlib.metadata as m; assert sys.version_info >= (3, 10); assert m.version("fastapi") == "0.128.2"; assert m.version("uvicorn") == "0.48.0"' >/dev/null 2>&1
}
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
  if ! compatible "$PY"; then
    "$PY" -m pip install -r requirements.txt
  fi
elif compatible python3; then
  PY=python3
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  PY=.venv/bin/python
fi
exec "$PY" -m backend "$@"
