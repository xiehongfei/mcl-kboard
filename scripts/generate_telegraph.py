#!/usr/bin/env python3
"""生成抗日谍片风格的莫尔斯电报「滴滴滴」音效（CW 边音）。"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packs" / "typewriter"
SR = 44100
FREQ = 700.0  # 典型电报边音频率 (Hz)


def tone(duration: float, freq: float = FREQ, amp: float = 0.85, fade_ms: float = 4.0) -> list[float]:
    n = max(1, int(SR * duration))
    fade = int(SR * fade_ms / 1000.0)
    out: list[float] = []
    for i in range(n):
        t = i / SR
        # 轻微谐波，更像电子管/耳机边音
        s = math.sin(2 * math.pi * freq * t)
        s += 0.18 * math.sin(2 * math.pi * freq * 2 * t)
        s += 0.06 * math.sin(2 * math.pi * freq * 3 * t)
        s *= amp / 1.24
        if i < fade:
            s *= i / max(1, fade)
        if i > n - fade:
            s *= (n - i) / max(1, fade)
        out.append(max(-1.0, min(1.0, s)))
    return out


def silence(duration: float) -> list[float]:
    return [0.0] * max(1, int(SR * duration))


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        frames = b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples
        )
        wf.writeframes(frames)


def main() -> None:
    sounds = ROOT / "sounds"
    if sounds.exists():
        for p in sounds.glob("*.wav"):
            p.unlink()
    sounds.mkdir(parents=True, exist_ok=True)

    # 点 (滴) / 划 (嗒) —— 标准莫尔斯比例约 1:3
    dot = tone(0.055, amp=0.75)
    dash = tone(0.16, amp=0.85)
    dot_soft = tone(0.045, freq=680, amp=0.55)
    dash_hard = tone(0.19, freq=720, amp=0.95)
    # 连续两滴（连发手感）
    double_dot = dot + silence(0.04) + tone(0.05, amp=0.7)
    # 收报结束长音 / 换行铃感：稍长划
    end_tone = tone(0.28, freq=650, amp=0.9)
    # 空格：短静音+划
    space = silence(0.02) + dash
    # 退格：略低沉短音
    back = tone(0.07, freq=520, amp=0.65)

    files = {
        "dot.wav": dot,
        "dot_soft.wav": dot_soft,
        "dash.wav": dash,
        "dash_hard.wav": dash_hard,
        "double_dot.wav": double_dot,
        "end.wav": end_tone,
        "space.wav": space,
        "backspace.wav": back,
    }
    for name, samples in files.items():
        write_wav(sounds / name, samples)

    cfg = {
        "name": "typewriter",
        "display_name": "电报机（莫尔斯滴滴）",
        "style": "typewriter",
        "description": "抗日谍片风格莫尔斯电码边音「滴滴滴」，非打字机敲击声",
        "default": "generic",
        "source": "generated CW sidetone (mcl-kboard)",
        "license": "MIT",
        "layers": {
            "soft": {
                "generic": ["sounds/dot_soft.wav"],
                "space": ["sounds/space.wav"],
                "enter": ["sounds/end.wav"],
                "backspace": ["sounds/backspace.wav"],
            },
            "mid": {
                "generic": ["sounds/dot.wav", "sounds/double_dot.wav"],
                "space": ["sounds/space.wav", "sounds/dash.wav"],
                "enter": ["sounds/end.wav"],
                "backspace": ["sounds/backspace.wav"],
            },
            "hard": {
                "generic": ["sounds/dash.wav", "sounds/dash_hard.wav"],
                "space": ["sounds/dash_hard.wav"],
                "enter": ["sounds/end.wav"],
                "backspace": ["sounds/backspace.wav"],
            },
        },
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote Morse telegraph pack → {ROOT}")


if __name__ == "__main__":
    main()
