"""CLI: start / stop / status / install / uninstall / menubar."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from . import __version__
from .accessibility import (
    accessibility_hint,
    is_trusted,
    open_accessibility_settings,
    python_app_path,
    request_trust_prompt,
    reveal_helpers_in_finder,
    reveal_python_in_finder,
    terminal_app_path,
    cursor_app_path,
)
from .pack_loader import list_pack_infos, list_packs, resolve_pack_id
from .paths import (
    AGENT_PID_PATH,
    BIN_LINK,
    FORCE_SOCK_FALLBACK,
    FORCE_SOCK_PATH,
    INSTALL_PREFIX,
    LAUNCH_DAEMON_LABEL,
    LAUNCH_DAEMON_PLIST,
    MENUBAR_PID_PATH,
    SUPPORT_DIR,
    default_packs_dir,
    ensure_support_dir,
    repo_root,
)
from .state import load_state, migrate_loud_defaults, save_state


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _stop_pidfile(path: Path, name: str) -> bool:
    pid = _read_pid(path)
    if pid is None:
        return False
    if not _pid_alive(pid):
        try:
            path.unlink()
        except OSError:
            pass
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    for _ in range(30):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        path.unlink()
    except OSError:
        pass
    print(f"stopped {name} (pid {pid})")
    return True


def cmd_status(_: argparse.Namespace) -> int:
    ensure_support_dir()
    state = load_state()
    agent_pid = _read_pid(AGENT_PID_PATH)
    menubar_pid = _read_pid(MENUBAR_PID_PATH)
    agent_on = bool(agent_pid and _pid_alive(agent_pid))
    menu_on = bool(menubar_pid and _pid_alive(menubar_pid))
    sock = FORCE_SOCK_PATH if FORCE_SOCK_PATH.exists() else FORCE_SOCK_FALLBACK
    imu_sock = sock.exists()
    daemon_loaded = False
    try:
        r = subprocess.run(
            ["launchctl", "print", f"system/{LAUNCH_DAEMON_LABEL}"],
            capture_output=True,
            text=True,
        )
        daemon_loaded = r.returncode == 0
    except OSError:
        pass

    print(f"mcl-kboard {__version__}")
    print(f"  enabled:     {state.enabled}")
    print(f"  volume:      {int(round(state.volume * 100))}% ({state.volume:.2f})")
    print(f"  pack:        {state.pack}")
    # show display name if available
    try:
        from .pack_loader import list_pack_infos

        info = next((i for i in list_pack_infos() if i.id == state.pack), None)
        if info:
            print(f"  style:       {info.label}")
    except Exception:
        pass
    print(f"  sensitivity: {state.sensitivity}")
    print(f"  accessibility: {'trusted ✓' if is_trusted() else 'NOT trusted ✗ (无按键音)'}")
    print(f"  agent:       {'running pid='+str(agent_pid) if agent_on else 'stopped'}")
    print(f"  menubar:     {'running pid='+str(menubar_pid) if menu_on else 'stopped'}")
    print(f"  imu socket:  {'up '+str(sock) if imu_sock else 'down'}")
    print(f"  imu daemon:  {'loaded' if daemon_loaded else 'not loaded (用 bash packaging/install.sh)'}")
    print(f"  packs:       {', '.join(list_packs()) or '(none)'}")
    print(f"  state file:  {SUPPORT_DIR / 'state.json'}")
    if not is_trusted():
        print()
        print("提示: 运行 mcl-kboard doctor 查看如何开启辅助功能")
    return 0


def _python() -> str:
    return sys.executable


def cmd_start(args: argparse.Namespace) -> int:
    ensure_support_dir()
    state = migrate_loud_defaults(load_state())
    state.enabled = True
    if args.pack:
        state.pack = args.pack
    if getattr(args, "volume", None) is not None:
        state.volume = args.volume
    save_state(state)

    if args.test_sound:
        _play_test_sound()

    if not is_trusted():
        print("⚠ 尚未获得「辅助功能」权限，启动后按键不会有声音。")
        print(accessibility_hint())
        request_trust_prompt()
        open_accessibility_settings()

    if getattr(args, "foreground", False):
        from .agent import main as agent_main

        if args.menubar:
            print("note: --foreground 下忽略 --menubar，请另开终端运行 mcl-kboard menubar")
        agent_main(["--pack", state.pack] if args.pack else None)
        return 0

    # Start agent if not running
    pid = _read_pid(AGENT_PID_PATH)
    if pid and _pid_alive(pid):
        print(f"agent already running (pid {pid})")
    else:
        log_path = SUPPORT_DIR / "agent.log"
        proc = subprocess.Popen(
            [_python(), "-m", "mcl_kboard.agent"],
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(repo_root()),
        )
        # agent writes its own pid; give it a moment
        time.sleep(0.3)
        print(f"started agent (spawn pid {proc.pid})")
        print(f"日志: {log_path}")

    if args.menubar:
        return cmd_menubar(args)

    # If IMU socket missing, hint
    if not FORCE_SOCK_PATH.exists() and not FORCE_SOCK_FALLBACK.exists():
        print(
            "提示: 未检测到 IMU force socket。\n"
            "  正式安装: bash packaging/install.sh\n"
            "  或: sudo .venv/bin/mcl-kboard install\n"
            "  开发模式: 另开终端运行 mcl-kboard imu --mock"
        )
    if not is_trusted():
        print("授权辅助功能后请执行: mcl-kboard stop && mcl-kboard start")
    return 0


def _play_test_sound() -> None:
    try:
        from .audio_engine import preview_pack

        state = load_state()
        print("播放测试音（soft → mid → hard）…")
        preview_pack(state.pack, volume=state.volume)
        print("若你听到三声点击，说明音频链路正常，问题多半是键盘权限。")
    except Exception as e:
        print(f"测试音失败: {e}")


def cmd_doctor(args: argparse.Namespace) -> int:
    ensure_support_dir()
    trusted = is_trusted()
    sock_ok = FORCE_SOCK_PATH.exists() or FORCE_SOCK_FALLBACK.exists()
    packs = list_packs()
    app = python_app_path()
    print("mcl-kboard doctor")
    print(f"  Python:        {sys.executable}")
    print(f"  需授权的 App:  {app}")
    print(f"  路径是否存在:  {'是 ✓' if app.exists() else '否 ✗'}")
    print(f"  辅助功能:      {'已授权 ✓' if trusted else '未授权 ✗  ← 无声音的常见原因'}")
    print(f"  IMU socket:    {'就绪 ✓' if sock_ok else '未就绪（开发请先 mcl-kboard imu --mock）'}")
    print(f"  音色包:        {', '.join(packs) or '无'}")
    print()
    print("找不到 Python.app？它在隐藏的系统目录里，请用下面任一方式：")
    print(f'  1) 终端执行: open -R "{app}"')
    print("  2) mcl-kboard doctor --reveal   （访达中显示，并打开系统设置）")
    print("  3) 系统设置 → 辅助功能 →「+」→ 按 ⌘⇧G，粘贴上述路径后回车")
    print(f"  另外可授权: {terminal_app_path()}")
    cur = cursor_app_path()
    if cur:
        print(f"             {cur}")

    if getattr(args, "reveal", False) or not trusted:
        ok = reveal_python_in_finder()
        if getattr(args, "reveal", False):
            reveal_helpers_in_finder()
            open_accessibility_settings()
            print()
            print("已尝试在访达中显示相关 App，并打开「辅助功能」设置页。")
            if not ok:
                print("警告：Python.app 路径不存在，请检查 Python 安装。")
        if not trusted:
            print()
            print(accessibility_hint())
            if not getattr(args, "reveal", False):
                reveal_python_in_finder()
                open_accessibility_settings()
            request_trust_prompt()
    return 0 if trusted and sock_ok and packs else 1


def cmd_stop(args: argparse.Namespace) -> int:
    ensure_support_dir()
    state = load_state()
    state.enabled = False
    save_state(state)

    _stop_pidfile(AGENT_PID_PATH, "agent")
    if args.menubar or args.full:
        _stop_pidfile(MENUBAR_PID_PATH, "menubar")

    if args.full:
        # Unload launch daemon if present
        if LAUNCH_DAEMON_PLIST.exists():
            subprocess.run(["sudo", "launchctl", "bootout", f"system/{LAUNCH_DAEMON_LABEL}"], check=False)
            print("requested IMU daemon stop (launchctl bootout)")
        # Also try local mock imu pid
        _stop_pidfile(Path("/tmp/mcl-kboard-imu.pid"), "imu(mock)")
    print("sound service disabled")
    return 0


def cmd_menubar(_: argparse.Namespace) -> int:
    ensure_support_dir()
    pid = _read_pid(MENUBAR_PID_PATH)
    if pid and _pid_alive(pid):
        print(f"menubar already running (pid {pid})")
        return 0
    log_path = SUPPORT_DIR / "menubar.log"
    proc = subprocess.Popen(
        [_python(), "-m", "mcl_kboard.menubar"],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    time.sleep(0.3)
    print(f"started menubar (spawn pid {proc.pid})")
    return 0


def cmd_imu(args: argparse.Namespace) -> int:
    from .imu_daemon import main as imu_main

    argv = []
    if args.mock:
        argv.append("--mock")
    if args.recording:
        argv.extend(["--recording", str(args.recording)])
    if args.verbose:
        argv.append("-v")
    imu_main(argv)
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    state = load_state()
    if args.volume is not None:
        state.volume = args.volume
    if args.sensitivity is not None:
        state.sensitivity = args.sensitivity
    if args.pack is not None:
        try:
            state.pack = resolve_pack_id(args.pack)
        except FileNotFoundError as e:
            print(e)
            return 1
    if args.enabled is not None:
        state.enabled = args.enabled
    save_state(state)
    if args.pack is not None:
        try:
            from .audio_engine import preview_pack

            print("试听三声…")
            preview_pack(state.pack, volume=state.volume)
        except Exception as e:
            print(f"试听失败: {e}")
    print("updated state:")
    cmd_status(args)
    return 0


def cmd_volume(args: argparse.Namespace) -> int:
    """手动调节音量：mcl-kboard volume / volume 80 / volume + / volume -"""
    state = load_state()
    if args.level is None:
        print(f"音量: {int(round(state.volume * 100))}%  (内部值 {state.volume:.2f}，范围 0~200%)")
        print("示例: mcl-kboard volume 80 | volume + | volume - | volume 150")
        return 0

    raw = args.level.strip()
    if raw in ("+", "up"):
        state.volume = min(2.0, round(state.volume + 0.1, 2))
    elif raw in ("-", "down"):
        state.volume = max(0.0, round(state.volume - 0.1, 2))
    else:
        try:
            val = float(raw.replace("%", ""))
        except ValueError:
            print(f"无效音量: {args.level}")
            return 1
        # 0-2 → 直接当作内部增益；>2 当作百分比
        if val > 2.0:
            val = val / 100.0
        state.volume = max(0.0, min(2.0, val))
    save_state(state)
    print(f"音量已设为 {int(round(state.volume * 100))}%")
    return 0


def cmd_style(args: argparse.Namespace) -> int:
    """列出或切换声源风格。"""
    infos = list_pack_infos()
    if args.name is None:
        state = load_state()
        print("可用声源风格：")
        for info in infos:
            mark = " *" if info.id == state.pack else "  "
            print(f"{mark} {info.id:18}  {info.label}")
            if info.description:
                print(f"     {info.description}")
        print()
        print("切换: mcl-kboard style typewriter")
        print("      mcl-kboard style cherry-mx-blue")
        print("      mcl-kboard style 电报机")
        return 0
    try:
        pack_id = resolve_pack_id(args.name)
    except FileNotFoundError as e:
        print(e)
        return 1
    state = load_state()
    state.pack = pack_id
    save_state(state)
    info = next((i for i in infos if i.id == pack_id), None)
    label = info.label if info else pack_id
    print(f"已切换声源: {label}")
    try:
        from .audio_engine import preview_pack

        print("试听三声…")
        preview_pack(pack_id, volume=state.volume)
    except Exception as e:
        print(f"试听失败: {e}")
    print("如 agent 已在运行，将自动热加载（或执行 mcl-kboard stop && mcl-kboard start）")
    return 0


def cmd_packs(_: argparse.Namespace) -> int:
    return cmd_style(argparse.Namespace(name=None))


def cmd_install(args: argparse.Namespace) -> int:
    if os.geteuid() != 0:
        # sudo 会重置 PATH，直接 `sudo mcl-kboard` 通常找不到命令
        exe = Path(sys.argv[0]).resolve()
        if not exe.exists():
            exe = Path(sys.executable).resolve().parent / "mcl-kboard"
        print("install 需要 root，且必须使用可执行文件的绝对路径。")
        print("请不要使用: sudo mcl-kboard install   ← sudo 清掉 PATH 后会 command not found")
        print()
        print("请改用下面任一方式：")
        print(f"  sudo {exe} install")
        print(f"  sudo {sys.executable} -m mcl_kboard.cli install")
        print("  bash packaging/install.sh")
        return 1

    root = repo_root()
    prefix = INSTALL_PREFIX
    prefix.mkdir(parents=True, exist_ok=True)

    # Create venv and install package
    venv = prefix / "venv"
    if not venv.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    pip = venv / "bin" / "pip"
    subprocess.check_call([str(pip), "install", "--upgrade", "pip"])
    subprocess.check_call([str(pip), "install", str(root)])

    # Copy packs
    packs_src = root / "packs"
    packs_dst = prefix / "packs"
    if packs_src.is_dir():
        if packs_dst.exists():
            shutil.rmtree(packs_dst)
        shutil.copytree(packs_src, packs_dst)

    # Wrapper script
    wrapper = f"""#!/bin/bash
exec "{venv}/bin/mcl-kboard" "$@"
"""
    BIN_LINK.parent.mkdir(parents=True, exist_ok=True)
    BIN_LINK.write_text(wrapper, encoding="utf-8")
    os.chmod(BIN_LINK, 0o755)

    # LaunchDaemon plist
    py = venv / "bin" / "python"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCH_DAEMON_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{py}</string>
    <string>-m</string>
    <string>mcl_kboard.imu_daemon</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/var/log/mcl-kboard-imu.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/mcl-kboard-imu.log</string>
</dict>
</plist>
"""
    LAUNCH_DAEMON_PLIST.write_text(plist, encoding="utf-8")
    os.chmod(LAUNCH_DAEMON_PLIST, 0o644)

    subprocess.run(["launchctl", "bootout", f"system/{LAUNCH_DAEMON_LABEL}"], check=False)
    subprocess.check_call(["launchctl", "bootstrap", "system", str(LAUNCH_DAEMON_PLIST)])
    subprocess.check_call(["launchctl", "enable", f"system/{LAUNCH_DAEMON_LABEL}"])
    subprocess.check_call(["launchctl", "kickstart", "-k", f"system/{LAUNCH_DAEMON_LABEL}"])

    print(f"installed to {prefix}")
    print(f"CLI: {BIN_LINK}")
    print(f"LaunchDaemon: {LAUNCH_DAEMON_PLIST}")
    print("安装完成后日常使用（无需再 sudo）：")
    print("  mcl-kboard start --menubar")
    print("  mcl-kboard stop")
    print("请为 /usr/local/mcl-kboard/venv/bin/python 或 Python.app 开启辅助功能。")
    return 0


def cmd_uninstall(_: argparse.Namespace) -> int:
    if os.geteuid() != 0:
        exe = Path(sys.argv[0]).resolve()
        print("uninstall 需要 root，请使用绝对路径：")
        print(f"  sudo {exe} uninstall")
        print("  或: sudo /usr/local/bin/mcl-kboard uninstall")
        return 1
    subprocess.run(["launchctl", "bootout", f"system/{LAUNCH_DAEMON_LABEL}"], check=False)
    if LAUNCH_DAEMON_PLIST.exists():
        LAUNCH_DAEMON_PLIST.unlink()
    if BIN_LINK.exists():
        BIN_LINK.unlink()
    if INSTALL_PREFIX.exists():
        shutil.rmtree(INSTALL_PREFIX)
    print("uninstalled system components")
    print(f"user state left at {SUPPORT_DIR} (remove manually if desired)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mcl-kboard",
        description="力度感应机械键盘音效（Apple Silicon）",
    )
    p.add_argument("--version", action="version", version=f"mcl-kboard {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status", help="查看服务状态")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("doctor", help="诊断无声音等问题")
    sp.add_argument(
        "--reveal",
        action="store_true",
        help="在访达中显示 Python.app / Terminal / Cursor，并打开辅助功能设置",
    )
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("start", help="启动播音 agent")
    sp.add_argument("--menubar", action="store_true", help="同时启动菜单栏")
    sp.add_argument("--pack", type=str, default=None, help="指定音色包")
    sp.add_argument("--volume", type=float, default=None, help="主音量 0~2（可大于1放大）")
    sp.add_argument("--foreground", action="store_true", help="前台运行 agent（便于看日志）")
    sp.add_argument("--test-sound", action="store_true", help="启动前播放测试音")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("stop", help="停止播音 agent")
    sp.add_argument("--full", action="store_true", help="同时停止 IMU 守护进程 / 菜单栏")
    sp.add_argument("--menubar", action="store_true", help="同时停止菜单栏")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("menubar", help="启动菜单栏控制器")
    sp.set_defaults(func=cmd_menubar)

    sp = sub.add_parser("imu", help="前台运行 IMU 力度守护进程")
    sp.add_argument("--mock", action="store_true", help="模拟加速度计（开发用，无需 root）")
    sp.add_argument("--recording", type=Path, default=None, help="回放 macimu 录制 CSV")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.set_defaults(func=cmd_imu)

    sp = sub.add_parser("set", help="修改偏好设置")
    sp.add_argument("--volume", type=float, default=None, help="音量 0~2")
    sp.add_argument("--sensitivity", type=float, default=None)
    sp.add_argument("--pack", type=str, default=None, help="音色包 id / 显示名 / 风格")
    sp.add_argument("--enabled", type=lambda s: s.lower() in ("1", "true", "yes", "on"), default=None)
    sp.set_defaults(func=cmd_set)

    sp = sub.add_parser("volume", help="手动调节音量")
    sp.add_argument("level", nargs="?", default=None, help="如 80、1.2、+、-")
    sp.set_defaults(func=cmd_volume)

    sp = sub.add_parser("style", help="列出或切换声源风格")
    sp.add_argument("name", nargs="?", default=None, help="音色包 id / 显示名 / typewriter")
    sp.set_defaults(func=cmd_style)

    sp = sub.add_parser("install", help="安装 LaunchDaemon 与 CLI（需要 sudo）")
    sp.set_defaults(func=cmd_install)

    sp = sub.add_parser("uninstall", help="卸载系统组件（需要 sudo）")
    sp.set_defaults(func=cmd_uninstall)

    sp = sub.add_parser("packs", help="列出音色包（同 style）")
    sp.set_defaults(func=cmd_packs)

    return p


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
