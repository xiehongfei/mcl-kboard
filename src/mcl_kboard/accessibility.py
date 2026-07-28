"""macOS Accessibility (辅助功能) helpers for keyboard monitoring."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def is_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def request_trust_prompt() -> bool:
    """Show the system Accessibility permission dialog if possible."""
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from Foundation import NSDictionary

        opts = NSDictionary.dictionaryWithDictionary_(
            {"AXTrustedCheckOptionPrompt": True}
        )
        return bool(AXIsProcessTrustedWithOptions(opts))
    except Exception:
        return is_trusted()


def python_app_path() -> Path:
    """Resolve the .app bundle macOS TCC usually lists for this interpreter."""
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app" or parent.name.endswith(".app"):
            return parent

    for parent in exe.parents:
        candidate = parent / "Resources" / "Python.app"
        if candidate.is_dir():
            return candidate

    for parent in exe.parents:
        if parent.name.startswith("Python") and (parent / "Python.app").is_dir():
            return parent / "Python.app"

    return exe


def terminal_app_path() -> Path:
    p = Path("/System/Applications/Utilities/Terminal.app")
    if p.is_dir():
        return p
    return Path("/Applications/Utilities/Terminal.app")


def cursor_app_path() -> Path | None:
    p = Path("/Applications/Cursor.app")
    return p if p.is_dir() else None


def accessibility_hint() -> str:
    app = python_app_path()
    term = terminal_app_path()
    cursor = cursor_app_path()
    lines = [
        "无法监听键盘：当前进程尚未获得「辅助功能」权限（因此不会有按键音）。",
        "",
        "请按以下步骤操作：",
        "  1. 打开：系统设置 → 隐私与安全性 → 辅助功能",
        "  2. 点击列表下方的「+」",
        "  3. 在弹出的文件选择窗口按 ⌘⇧G（前往文件夹），粘贴下面路径后回车：",
        f"     {app}",
        "     （该目录在访达里默认隐藏，不能靠鼠标一层层点进去）",
        "  4. 选中 Python.app → 打开，并打开右侧开关",
        f"  5. 同样建议添加并开启：{term}",
    ]
    if cursor:
        lines.append(f"     以及：{cursor}")
    lines += [
        "  6. 然后执行：mcl-kboard stop && mcl-kboard start",
        "",
        "一键在访达中显示 Python.app：",
        "  mcl-kboard doctor --reveal",
        "或：",
        f'  open -R "{app}"',
        "",
        "开发时可前台运行看报错：mcl-kboard start --foreground",
    ]
    return "\n".join(lines)


def open_accessibility_settings() -> None:
    urls = [
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Accessibility",
    ]
    for url in urls:
        try:
            subprocess.run(["open", url], check=False)
            return
        except OSError:
            continue


def reveal_python_in_finder() -> bool:
    """Reveal Python.app in Finder. Returns True if path exists."""
    app = python_app_path()
    if not app.exists():
        return False
    try:
        subprocess.run(["open", "-R", str(app)], check=False)
        return True
    except OSError:
        return False


def reveal_helpers_in_finder() -> None:
    """Reveal Python.app, Terminal, Cursor for easy drag into Accessibility."""
    reveal_python_in_finder()
    for p in (terminal_app_path(), cursor_app_path()):
        if p and p.exists():
            try:
                subprocess.run(["open", "-R", str(p)], check=False)
            except OSError:
                pass
