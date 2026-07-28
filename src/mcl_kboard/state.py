"""Persistent user preferences."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .paths import STATE_PATH, ensure_support_dir


@dataclass
class AppState:
    enabled: bool = True
    volume: float = 1.0  # master; may exceed 1.0 for boost (clamped to 2.0)
    pack: str = "cherry-mx-blue"
    sensitivity: float = 1.35
    gamma: float = 1.15  # >1 = more soft/hard contrast
    min_gain: float = 0.4
    max_gain: float = 1.0
    a_hard: float = 0.12  # initial; agent auto-calibrates from peaks
    mute_modifiers: bool = True
    align_window_ms: float = 45.0
    default_velocity: float = 0.55

    def clamp(self) -> AppState:
        self.volume = float(max(0.0, min(2.0, self.volume)))
        self.sensitivity = float(max(0.2, min(4.0, self.sensitivity)))
        self.gamma = float(max(0.4, min(2.5, self.gamma)))
        self.min_gain = float(max(0.05, min(1.5, self.min_gain)))
        self.max_gain = float(max(self.min_gain, min(2.0, self.max_gain)))
        self.a_hard = float(max(0.003, min(2.0, self.a_hard)))
        self.align_window_ms = float(max(8.0, min(100.0, self.align_window_ms)))
        self.default_velocity = float(max(0.0, min(1.0, self.default_velocity)))
        return self


def load_state(path: Path | None = None) -> AppState:
    p = path or STATE_PATH
    ensure_support_dir()
    if not p.exists():
        state = AppState().clamp()
        save_state(state, p)
        return state
    try:
        raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppState().clamp()
    known = {f.name for f in fields(AppState)}
    filtered = {k: v for k, v in raw.items() if k in known}
    return AppState(**filtered).clamp()


def save_state(state: AppState, path: Path | None = None) -> None:
    p = path or STATE_PATH
    ensure_support_dir()
    p.write_text(json.dumps(asdict(state.clamp()), indent=2) + "\n", encoding="utf-8")


def migrate_loud_defaults(state: AppState) -> AppState:
    """Bump older quiet defaults once so existing installs get louder playback."""
    changed = False
    if state.volume <= 0.75:
        state.volume = 1.0
        changed = True
    if state.min_gain <= 0.3:
        state.min_gain = 0.4
        changed = True
    if state.sensitivity < 1.2:
        state.sensitivity = 1.35
        changed = True
    if state.gamma < 1.0:
        state.gamma = 1.15
        changed = True
    if state.a_hard >= 0.3:
        # Old fixed 0.35 crushed mock/real small peaks to ~0 velocity
        state.a_hard = 0.12
        changed = True
    if state.align_window_ms < 40:
        state.align_window_ms = 45.0
        changed = True
    if state.default_velocity < 0.5:
        state.default_velocity = 0.55
        changed = True
    if changed:
        save_state(state)
    return state
