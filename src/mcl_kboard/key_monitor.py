"""Global keyboard event monitor (requires Accessibility on macOS)."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, Set

log = logging.getLogger("mcl_kboard.keys")

MODIFIER_NAMES = {
    "cmd",
    "command",
    "ctrl",
    "control",
    "alt",
    "option",
    "shift",
    "caps_lock",
    "cmd_r",
    "ctrl_r",
    "alt_r",
    "shift_r",
}


KeyHandler = Callable[[str, float], None]


class KeyMonitor:
    def __init__(self, on_keydown: KeyHandler, mute_modifiers: bool = True):
        self.on_keydown = on_keydown
        self.mute_modifiers = mute_modifiers
        self._listener = None
        self._pressed: Set[str] = set()

    def start(self) -> None:
        from pynput import keyboard

        def _name(key: object) -> str:
            try:
                if hasattr(key, "char") and key.char:  # type: ignore[attr-defined]
                    return str(key.char).lower()
            except Exception:
                pass
            text = str(key)
            # Key.space -> space
            if text.startswith("Key."):
                return text[4:].lower()
            return text.lower()

        def on_press(key: object) -> None:
            name = _name(key)
            if name in self._pressed:
                return  # key repeat
            self._pressed.add(name)
            if self.mute_modifiers and name in MODIFIER_NAMES:
                return
            try:
                self.on_keydown(name, time.monotonic())
            except Exception:
                log.exception("keydown handler error")

        def on_release(key: object) -> None:
            name = _name(key)
            self._pressed.discard(name)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        log.info("key monitor started")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None


def accessibility_hint() -> str:
    from .accessibility import accessibility_hint as _hint

    return _hint()
