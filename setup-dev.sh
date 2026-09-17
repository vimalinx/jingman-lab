#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v python3 >/dev/null
command -v node >/dev/null
command -v npm >/dev/null
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -r requirements-test.txt -r requirements-import.txt -r requirements-integrations.txt
else
  .venv/bin/python -m pip install -r requirements-test.txt -r requirements-import.txt -r requirements-integrations.txt
fi
# Official CI is a development dependency, never a production server dependency.
npm ci --ignore-scripts --no-fund
npm run doctor
npm run ci:check
