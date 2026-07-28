"""Force / velocity mapping utilities."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def map_amplitude_to_velocity(
    amplitude: float,
    *,
    noise_floor: float,
    a_hard: float,
    sensitivity: float = 1.0,
    gamma: float = 1.15,
) -> float:
    """Map dynamic accel magnitude (g) to [0, 1] typing velocity.

    gamma > 1 expands contrast (soft stays softer, hard gets relatively louder).
    """
    span = max(1e-9, a_hard - noise_floor)
    raw = (amplitude - noise_floor) / span
    raw *= sensitivity
    v = clamp(raw)
    return float(v**gamma)


def velocity_to_gain(velocity: float, min_gain: float, max_gain: float) -> float:
    v = clamp(velocity)
    # Extra contrast curve on the way to gain
    shaped = v * v * (3.0 - 2.0 * v)  # smoothstep — mid more separated from soft
    return min_gain + shaped * (max_gain - min_gain)


def velocity_to_layer(velocity: float) -> str:
    if velocity < 0.34:
        return "soft"
    if velocity < 0.67:
        return "mid"
    return "hard"


LAYER_GAIN = {
    "soft": 0.55,
    "mid": 0.95,
    "hard": 1.45,
}


@dataclass
class ForceSample:
    t: float  # seconds (monotonic / hardware clock)
    a: float  # magnitude in g


class AdaptiveNoiseFloor:
    """Estimate resting vibration level from a rolling low percentile."""

    def __init__(self, window: int = 400, percentile: float = 0.2, min_floor: float = 1e-5):
        self.window = window
        self.percentile = percentile
        self.min_floor = min_floor
        self._buf: Deque[float] = deque(maxlen=window)
        self.floor = min_floor

    def update(self, amplitude: float) -> float:
        self._buf.append(amplitude)
        if len(self._buf) < 20:
            return self.floor
        ordered = sorted(self._buf)
        idx = int(len(ordered) * self.percentile)
        idx = max(0, min(len(ordered) - 1, idx))
        self.floor = max(self.min_floor, ordered[idx] * 1.15)
        return self.floor


class AdaptiveHardScale:
    """Learn typical hard-hit amplitude from recent keystroke peaks."""

    def __init__(self, initial: float = 0.12, min_hard: float = 0.008, max_hard: float = 1.5):
        self.a_hard = initial
        self.min_hard = min_hard
        self.max_hard = max_hard
        self._peaks: Deque[float] = deque(maxlen=80)

    def observe(self, peak: float) -> float:
        if peak <= 0:
            return self.a_hard
        self._peaks.append(peak)
        if len(self._peaks) < 5:
            # Bootstrap: keep scale a bit above max so far so early hits aren't all "hard"
            self.a_hard = clamp(max(self.a_hard, peak * 1.8), self.min_hard, self.max_hard)
            return self.a_hard
        ordered = sorted(self._peaks)
        # Use ~85th percentile as "hard" reference so hard presses reach ~1.0
        idx = int(len(ordered) * 0.85)
        idx = max(0, min(len(ordered) - 1, idx))
        target = max(ordered[idx], ordered[-1] * 0.7)
        # EMA so it adapts without jumping
        self.a_hard = 0.85 * self.a_hard + 0.15 * target
        self.a_hard = clamp(self.a_hard, self.min_hard, self.max_hard)
        return self.a_hard


class ForceRing:
    """Ring buffer of recent force samples for key-event alignment."""

    def __init__(self, capacity: int = 512):
        self._buf: Deque[ForceSample] = deque(maxlen=capacity)

    def __len__(self) -> int:
        return len(self._buf)

    def push(self, sample: ForceSample) -> None:
        self._buf.append(sample)

    def max_since_index(self, start_index: int) -> Optional[float]:
        """Max amplitude among samples appended after start_index (by count)."""
        buf = list(self._buf)
        if not buf:
            return None
        # start_index is the length at keydown; only look at samples after that
        n_new = max(0, len(buf) - start_index)
        if n_new <= 0:
            return None
        tail = buf[-n_new:]
        return max(s.a for s in tail)

    def max_in_window(self, t0: float, window_s: float) -> float | None:
        lo = t0 - 0.005
        hi = t0 + window_s
        peak: float | None = None
        for s in self._buf:
            if lo <= s.t <= hi:
                if peak is None or s.a > peak:
                    peak = s.a
        return peak

    def latest(self) -> ForceSample | None:
        return self._buf[-1] if self._buf else None

    def signal_scale(self) -> float:
        """Rough dynamic range of recent stream (for mock detection)."""
        if len(self._buf) < 30:
            return 0.0
        vals = [s.a for s in self._buf]
        return max(vals) - min(vals)

    def clear(self) -> None:
        self._buf.clear()


class PeakGate:
    """Suppress duplicate peaks from a single physical impact."""

    def __init__(self, min_spacing_s: float = 0.025):
        self.min_spacing_s = min_spacing_s
        self._last_t = -math.inf
        self._last_a = 0.0

    def accept(self, t: float, a: float, threshold: float) -> bool:
        if a < threshold:
            return False
        if t - self._last_t < self.min_spacing_s and a < self._last_a * 1.2:
            return False
        self._last_t = t
        self._last_a = a
        return True


def high_pass_magnitude(prev_y: float, prev_x: float, current: float, alpha: float = 0.85) -> tuple[float, float]:
    """Simple 1-pole high-pass on scalar magnitude. Returns (y_n, x_n)."""
    y = alpha * (prev_y + current - prev_x)
    return y, current
