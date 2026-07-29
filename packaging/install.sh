#!/bin/bash
# 正式安装：LaunchDaemon + /usr/local/bin/mcl-kboard
#
# 注意：不要使用 `sudo mcl-kboard install`
# sudo 会清空 PATH，导致 command not found。
#
# 用法（在仓库根目录）:
#   bash packaging/install.sh
#   # 或:
#   source .venv/bin/activate && sudo "$(pwd)/.venv/bin/mcl-kboard" install
#
# 代码更新后请重新执行本脚本，否则 /usr/local 仍是旧版
# （例如旧版菜单栏会在启动时崩溃，表现为「提示已启动但图标不出现」）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/.venv/bin/mcl-kboard"

if [[ ! -x "$BIN" ]]; then
  echo "未找到 $BIN"
  echo "请先："
  echo "  cd \"$ROOT\""
  echo "  python3 -m venv .venv && source .venv/bin/activate"
  echo "  pip install -e \".[dev]\""
  exit 1
fi

echo "将执行: sudo $BIN install"
echo "（会更新 /usr/local/mcl-kboard 中的代码与音色包）"
exec sudo "$BIN" install
