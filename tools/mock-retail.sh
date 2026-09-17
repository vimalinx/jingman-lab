#!/usr/bin/env bash
# Local synthetic demo only. Never invokes the real-provider adapter.
set -euo pipefail
jingman_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$jingman_root"
if [[ ! -x .venv/bin/python ]]; then
  echo '请先运行本工程 setup-dev.sh 安装依赖。' >&2
  exit 2
fi
if (( $# > 1 )); then
  echo '用法：bash tools/mock-retail.sh [源码之外的模拟专用目录绝对路径]' >&2
  exit 2
fi
exec .venv/bin/python -m backend.mock_demo "${1:-${XDG_STATE_HOME:-$HOME/.local/state}/jingman-local-mock}"
