#!/usr/bin/env bash
# Thin entry point: no automatic authorization, installation, or retries.
set -euo pipefail
umask 077
jingman_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$jingman_root"

usage() {
  printf '%s\n' \
    '用法：bash /绝对路径/tools/lakala-connect.sh check [配置文件绝对路径]' \
    '      bash /绝对路径/tools/lakala-connect.sh query 配置文件绝对路径 授权条码 新回执目录绝对路径' \
    'check 默认不联网、不读取私钥；query 仅调用一次拉卡拉测试商品查询，不同步库存或订单。'
}

case "${1:-check}" in
  -h|--help|help) usage; exit 0 ;;
  check)
    if (( $# > 2 )); then usage >&2; exit 2; fi
    lakala_config="${2:-$jingman_root/config/lakala-retail.example.json}"
    lakala_args=(--config "$lakala_config")
    ;;
  query)
    if (( $# != 4 )); then usage >&2; exit 2; fi
    lakala_config="$2"
    if [[ "$4" != /* ]]; then printf '%s\n' '回执目录必须是全新的绝对路径。' >&2; exit 2; fi
    lakala_args=(--config "$lakala_config" --barcode "$3" --output "$4" --execute)
    ;;
  *) usage >&2; exit 2 ;;
esac

if [[ "$lakala_config" != /* ]]; then
  printf '%s\n' '配置文件必须使用绝对路径，避免切换目录后读错配置。' >&2
  exit 2
fi
if [[ ! -x "$jingman_root/.venv/bin/python" ]]; then
  printf '%s\n' '缺少项目 .venv；请先按 docs/LAKALA-CONNECT.md 安装依赖。' >&2
  exit 2
fi
exec "$jingman_root/.venv/bin/python" -m backend.lakala_readonly "${lakala_args[@]}"
