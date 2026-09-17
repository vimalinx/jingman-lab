#!/usr/bin/env bash
set -euo pipefail
# This machine's reusable, isolated manual-acceptance environment; no production data.
unit=jingman-manual-acceptance.service
case "${1:-start}" in
  start)
    systemctl --user start "$unit"
    ready=false
    for attempt in {1..50}; do
      if curl --fail --silent --max-time 1 http://127.0.0.1:8870/api/health >/dev/null; then
        ready=true
        break
      fi
      sleep 0.2
    done
    if [[ "$ready" != true ]]; then
      printf '%s\n' '服务尚未就绪，请运行 manual-acceptance.sh status 查看状态。' >&2
      exit 1
    fi
    systemctl --user is-active --quiet "$unit"
    printf '%s\n' '人工验收服务已启动：http://127.0.0.1:8870/' \
      '仅本机、模拟支付；退款/打印请在实验室手动重试。' \
      '需要登录口令时：bash /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/tools/manual-acceptance.sh key'
    ;;
  status) systemctl --user status "$unit" --no-pager ;;
  stop) systemctl --user stop "$unit" ;;
  open)
    bash "$0" start
    xdg-open http://127.0.0.1:8870/
    ;;
  key)
    # Explicit human-requested display only; never embed in source, URLs, or logs.
    /home/vimalinx/MakeMoney/SuperMarket/jingman-lab/.venv/bin/python -c \
      'import json; print(json.load(open("/home/vimalinx/.local/state/jingman-manual-20260915-I7qICCma/credentials.json"))["access_key"])'
    ;;
  *) printf '%s\n' '用法：manual-acceptance.sh [start|status|stop|open|key]' >&2; exit 2 ;;
esac
