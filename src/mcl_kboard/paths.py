"""Filesystem paths and constants for mcl-kboard."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "mcl-kboard"
BUNDLE_ID = "com.mcl.kboard"

# User-writable state / logs
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
STATE_PATH = SUPPORT_DIR / "state.json"
AGENT_PID_PATH = SUPPORT_DIR / "agent.pid"
AGENT_LOG_PATH = SUPPORT_DIR / "agent.log"
MENUBAR_PID_PATH = SUPPORT_DIR / "menubar.pid"

# Shared force socket (world-readable for user agent; written by root daemon)
FORCE_SOCK_DIR = Path("/var/run/mcl-kboard")
FORCE_SOCK_PATH = FORCE_SOCK_DIR / "force.sock"
# Fallback when /var/run is not writable (dev / mock mode)
FORCE_SOCK_FALLBACK = Path("/tmp/mcl-kboard-force.sock")

IMU_PID_PATH = Path("/var/run/mcl-kboard/imu.pid")
IMU_LOG_PATH = Path("/var/log/mcl-kboard-imu.log")

LAUNCH_DAEMON_LABEL = "com.mcl.kboard.imu"
LAUNCH_DAEMON_PLIST = Path(f"/Library/LaunchDaemons/{LAUNCH_DAEMON_LABEL}.plist")

INSTALL_PREFIX = Path("/usr/local/mcl-kboard")
BIN_LINK = Path("/usr/local/bin/mcl-kboard")


def package_root() -> Path:
    return Path(__file__).resolve().parent


def menubar_icon_path() -> Path:
    """Template PNG for rumps status item (macOS adapts light/dark)."""
    return package_root() / "assets" / "MenubarIconTemplate.png"


def repo_root() -> Path:
    return package_root().parent.parent


def default_packs_dir() -> Path:
    """Prefer installed packs, then repo packs/."""
    installed = INSTALL_PREFIX / "packs"
    if installed.is_dir():
        return installed
    repo = repo_root() / "packs"
    if repo.is_dir():
        return repo
    return package_root() / "packs"


def ensure_support_dir() -> Path:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    return SUPPORT_DIR


def resolve_force_sock() -> Path:
    if FORCE_SOCK_PATH.exists() or os.geteuid() == 0:
        return FORCE_SOCK_PATH
    return FORCE_SOCK_FALLBACK
