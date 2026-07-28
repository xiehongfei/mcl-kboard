"""Low-latency multi-voice keyboard sound playback with software mixing."""

from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .force import LAYER_GAIN, velocity_to_gain, velocity_to_layer
from .pack_loader import SoundPack
from .state import AppState

log = logging.getLogger("mcl_kboard.audio")

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None  # type: ignore


class AudioEngine:
    """Overlapping sample player using a persistent OutputStream mixer."""

    def __init__(self, sample_rate: int = 44100, blocksize: int = 256):
        if sd is None:
            raise RuntimeError("sounddevice is required for audio playback")
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self._cache: Dict[Path, np.ndarray] = {}
        self._lock = threading.Lock()
        self._voices: List[Tuple[np.ndarray, int]] = []  # (samples, cursor)
        self._pack: Optional[SoundPack] = None
        self.volume = 1.0
        self._stream: Optional[sd.OutputStream] = None
        self._start_stream()

    def _start_stream(self) -> None:
        def callback(outdata: np.ndarray, frames: int, _time: object, status: object) -> None:
            if status:
                log.debug("audio status: %s", status)
            mix = np.zeros(frames, dtype=np.float32)
            with self._lock:
                alive: List[Tuple[np.ndarray, int]] = []
                for samples, cursor in self._voices:
                    end = cursor + frames
                    chunk = samples[cursor:end]
                    mix[: len(chunk)] += chunk
                    if end < len(samples):
                        alive.append((samples, end))
                self._voices = alive
            # Soft clip with light saturation so loud hits stay punchy
            mix = np.tanh(mix * 1.15) / np.tanh(1.15)
            outdata[:, 0] = mix.astype(np.float32)

        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.blocksize,
            callback=callback,
        )
        self._stream.start()

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def set_pack(self, pack: SoundPack) -> None:
        self._pack = pack
        with self._lock:
            self._cache.clear()
        paths = set()
        for layer_map in pack.layered.values():
            for plist in layer_map.values():
                paths.update(plist)
        for plist in pack.flat.values():
            paths.update(plist)
        for p in list(paths)[:64]:
            try:
                self._load(p)
            except Exception as e:
                log.warning("preload failed %s: %s", p, e)

    def _load(self, path: Path) -> np.ndarray:
        with self._lock:
            cached = self._cache.get(path)
            if cached is not None:
                return cached
        data, sr = _read_wav(path)
        if sr != self.sample_rate:
            data = _resample(data, sr, self.sample_rate)
        data = _peak_normalize(data, target=0.95)
        with self._lock:
            self._cache[path] = data
        return data

    def play_key(self, key_id: str, velocity: float, state: AppState) -> None:
        if self._pack is None:
            return
        layer = velocity_to_layer(velocity)
        path = self._pack.pick(key_id, layer=layer)
        if path is None:
            return
        try:
            data = self._load(path)
        except Exception as e:
            log.warning("load failed %s: %s", path, e)
            return

        gain = velocity_to_gain(velocity, state.min_gain, state.max_gain)
        gain *= LAYER_GAIN.get(layer, 1.0)
        gain *= 1.0 + random.uniform(-0.04, 0.04)
        # Hard hits: slightly brighter / shorter attack feel via tiny pitch up
        pitch = 1.0 + (velocity - 0.5) * 0.04 + random.uniform(-0.01, 0.01)
        out = data * (gain * self.volume)
        if abs(pitch - 1.0) > 1e-4:
            out = _change_pitch(out, pitch)
        out = np.clip(out, -1.0, 1.0).astype(np.float32)
        with self._lock:
            if len(self._voices) > 24:
                self._voices = self._voices[-16:]
            self._voices.append((out, 0))
        log.debug("play key=%s vel=%.2f layer=%s gain=%.2f", key_id, velocity, layer, gain * self.volume)


def _peak_normalize(data: np.ndarray, target: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(data))) if len(data) else 0.0
    if peak < 1e-6:
        return data.astype(np.float32)
    return (data * (target / peak)).astype(np.float32)


def _read_wav(path: Path) -> Tuple[np.ndarray, int]:
    import wave

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(n)

    if sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sw == 1:
        audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw}")

    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return audio, sr


def _resample(data: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return data
    duration = len(data) / src
    n_out = max(1, int(duration * dst))
    x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, data).astype(np.float32)


def _change_pitch(data: np.ndarray, factor: float) -> np.ndarray:
    if factor == 1.0 or len(data) < 2:
        return data
    n_out = max(1, int(len(data) / factor))
    x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, data).astype(np.float32)


def preview_pack(
    pack_id: str,
    volume: float = 1.0,
    velocities: Tuple[float, ...] = (0.3, 0.6, 0.95),
    gap: float = 0.16,
) -> None:
    """Play a short audition of a sound pack (default: 3 taps soft→hard)."""
    import time

    from .pack_loader import load_pack

    engine = AudioEngine()
    try:
        engine.set_pack(load_pack(pack_id))
        engine.volume = volume
        st = AppState()
        for v in velocities:
            engine.play_key("generic", v, st)
            time.sleep(gap)
        time.sleep(0.28)
    finally:
        engine.close()


def preview_pack_async(pack_id: str, volume: float = 1.0) -> None:
    """Non-blocking audition (for menubar UI thread)."""

    def _run() -> None:
        try:
            preview_pack(pack_id, volume=volume)
        except Exception as e:  # pragma: no cover
            log.warning("preview failed: %s", e)

    threading.Thread(target=_run, daemon=True).start()
