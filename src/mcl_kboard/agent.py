"""User-space agent: align keydowns with force peaks and play sounds."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from .accessibility import accessibility_hint, is_trusted, request_trust_prompt
from .audio_engine import AudioEngine
from .force import AdaptiveHardScale, map_amplitude_to_velocity
from .force_client import ForceClient
from .key_monitor import KeyMonitor
from .pack_loader import list_packs, load_pack
from .paths import (
    AGENT_LOG_PATH,
    AGENT_PID_PATH,
    ensure_support_dir,
)
from .state import AppState, load_state, migrate_loud_defaults, save_state

log = logging.getLogger("mcl_kboard.agent")

CTRL_SOCK = Path("/tmp/mcl-kboard-force-ctrl.sock")


class Agent:
    def __init__(self, state: Optional[AppState] = None, packs_dir: Optional[Path] = None):
        self.state = migrate_loud_defaults(state or load_state())
        self.packs_dir = packs_dir
        self.force = ForceClient()
        self.audio = AudioEngine()
        self.keys: Optional[KeyMonitor] = None
        self._stop = threading.Event()
        self._reload_lock = threading.Lock()
        self._pending: List[tuple[str, float, int]] = []
        self._pending_lock = threading.Lock()
        self._align_thread: Optional[threading.Thread] = None
        self._state_mtime: float = 0.0
        self._warned_untrusted = False
        self._warned_mock = False
        self._hard = AdaptiveHardScale(initial=self.state.a_hard)
        self._last_play_t = 0.0
        self._last_vel_log_t = 0.0

    def _load_pack(self) -> None:
        pack = load_pack(self.state.pack, self.packs_dir)
        self.audio.set_pack(pack)
        self.audio.volume = self.state.volume
        log.info("loaded pack %s (layers=%s) volume=%.2f", pack.name, pack.has_layers(), self.state.volume)

    def start(self) -> None:
        ensure_support_dir()
        AGENT_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
        self._load_pack()
        self.force.start()

        if not is_trusted():
            request_trust_prompt()
            log.error("%s", accessibility_hint())
            print(accessibility_hint(), file=sys.stderr)

        def on_key(key_id: str, t: float) -> None:
            if not self.state.enabled:
                return
            # Snapshot ring length so we only score peaks AFTER this keydown
            idx = len(self.force.ring)
            with self._pending_lock:
                self._pending.append((key_id, t, idx))

        self.keys = KeyMonitor(on_key, mute_modifiers=self.state.mute_modifiers)
        try:
            self.keys.start()
        except Exception as e:
            log.error("Failed to start key monitor: %s\n%s", e, accessibility_hint())
            raise

        self._align_thread = threading.Thread(target=self._align_loop, daemon=True)
        self._align_thread.start()
        log.info("agent running (accessibility_trusted=%s)", is_trusted())

    def _maybe_reload_state(self) -> None:
        from .paths import STATE_PATH

        try:
            mtime = STATE_PATH.stat().st_mtime
        except OSError:
            return
        if mtime <= self._state_mtime:
            return
        self._state_mtime = mtime
        new_state = load_state()
        with self._reload_lock:
            old_pack = self.state.pack
            self.state = new_state
            self.audio.volume = self.state.volume
            if self.state.pack != old_pack:
                try:
                    self._load_pack()
                except Exception:
                    log.exception("pack reload failed")

    def _request_mock_tap(self) -> None:
        """Ask mock IMU daemon to inject a typing impulse (dev only)."""
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            s.settimeout(0.05)
            # Amplitude span covering soft→hard after auto-cal
            import random

            amp = random.uniform(0.02, 0.18)
            s.sendto(json.dumps({"cmd": "tap", "a": amp}).encode(), str(CTRL_SOCK))
            s.close()
        except OSError:
            pass

    def _align_loop(self) -> None:
        last_trust_check = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_trust_check > 5.0:
                last_trust_check = now
                if not is_trusted() and not self._warned_untrusted:
                    self._warned_untrusted = True
                    log.error("仍无辅助功能权限，按键不会触发声音。\n%s", accessibility_hint())
                elif is_trusted():
                    self._warned_untrusted = False

                scale = self.force.ring.signal_scale()
                if scale < 0.015 and self.force.connected and not self._warned_mock:
                    self._warned_mock = True
                    msg = (
                        "检测到 IMU 信号几乎无动态范围（多为 imu --mock）。"
                        "真实敲击力度需要真实加速度计：\n"
                        "  bash packaging/install.sh\n"
                        "  或: sudo .venv/bin/mcl-kboard imu\n"
                        "  然后: mcl-kboard stop && mcl-kboard start\n"
                        "mock 模式下将注入演示用冲击脉冲，力度仅为随机演示。"
                    )
                    log.warning("%s", msg)
                    print(msg, file=sys.stderr)

            self._maybe_reload_state()
            item = None
            with self._pending_lock:
                if self._pending:
                    item = self._pending.pop(0)
            if item is None:
                time.sleep(0.001)
                continue

            key_id, _t_key, start_idx = item
            weak_signal = self.force.ring.signal_scale() < 0.015
            if weak_signal:
                self._request_mock_tap()

            window_s = self.state.align_window_ms / 1000.0
            deadline = time.monotonic() + window_s
            peak: Optional[float] = None

            while time.monotonic() < deadline and not self._stop.is_set():
                peak = self.force.ring.max_since_index(start_idx)
                if peak is not None and peak > self._hard.a_hard * 0.45:
                    break
                time.sleep(0.001)

            if peak is None:
                peak = self.force.ring.max_since_index(start_idx)

            if peak is None or peak <= 0:
                velocity = self.state.default_velocity
            else:
                floor = self._estimate_floor()
                # Ignore peaks that are basically noise
                if peak <= floor * 1.05 and not weak_signal:
                    velocity = self.state.default_velocity * 0.7
                else:
                    a_hard = self._hard.observe(peak)
                    velocity = map_amplitude_to_velocity(
                        peak,
                        noise_floor=floor,
                        a_hard=a_hard,
                        sensitivity=self.state.sensitivity,
                        gamma=self.state.gamma,
                    )

            now = time.monotonic()
            if now - self._last_play_t < 0.008:
                continue
            self._last_play_t = now

            if now - self._last_vel_log_t > 0.4:
                self._last_vel_log_t = now
                log.info(
                    "key=%s peak=%.4f vel=%.2f a_hard=%.4f vol=%.2f",
                    key_id,
                    peak or 0.0,
                    velocity,
                    self._hard.a_hard,
                    self.state.volume,
                )

            try:
                self.audio.play_key(key_id, velocity, self.state)
            except Exception:
                log.exception("play failed")

    def _estimate_floor(self) -> float:
        buf = list(self.force.ring._buf)  # noqa: SLF001
        if len(buf) < 10:
            return 1e-4
        vals = sorted(s.a for s in buf)
        idx = max(0, int(len(vals) * 0.2))
        return max(1e-5, vals[idx] * 1.1)

    def stop(self) -> None:
        self._stop.set()
        if self.keys:
            self.keys.stop()
        self.force.stop()
        try:
            self.audio.close()
        except Exception:
            pass
        try:
            if AGENT_PID_PATH.exists():
                AGENT_PID_PATH.unlink()
        except OSError:
            pass
        log.info("agent stopped")

    def run_forever(self) -> int:
        self.start()

        def _sig(_s: int, _f: object) -> None:
            self._stop.set()

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
        while not self._stop.is_set():
            time.sleep(0.2)
        self.stop()
        return 0


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="mcl-kboard user agent")
    parser.add_argument("--pack", type=str, default=None)
    parser.add_argument("--packs-dir", type=Path, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    ensure_support_dir()
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        handlers.append(logging.FileHandler(AGENT_LOG_PATH))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )

    state = migrate_loud_defaults(load_state())
    if args.pack:
        state.pack = args.pack
        save_state(state)

    if args.pack is None and state.pack not in list_packs(args.packs_dir):
        packs = list_packs(args.packs_dir)
        if packs:
            state.pack = packs[0]
            save_state(state)

    agent = Agent(state=state, packs_dir=args.packs_dir)
    raise SystemExit(agent.run_forever())


if __name__ == "__main__":
    main()
