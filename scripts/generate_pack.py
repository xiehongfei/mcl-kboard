#!/usr/bin/env python3
"""已弃用：旧版会生成合成「叮叮」音。

请改用真实机械键盘录音：

  python scripts/fetch_real_packs.py
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "此脚本已弃用（会生成合成音，不是真实机械键盘声）。\n"
        "请运行：\n"
        "  python scripts/fetch_real_packs.py\n"
        "拉取 Cherry MX Blue / NK Cream / Holy Panda 真实录音（MIT）。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
