"""Alignment / pack loading tests."""

from __future__ import annotations

from pathlib import Path

from mcl_kboard.pack_loader import load_pack, list_packs
from mcl_kboard.state import AppState, load_state, save_state


def test_list_and_load_pack():
    packs = list_packs()
    assert "cherry-mx-blue" in packs
    pack = load_pack("cherry-mx-blue")
    assert pack.has_layers()
    soft = pack.pick("generic", "soft")
    hard = pack.pick("generic", "hard")
    assert soft is not None and soft.exists()
    assert hard is not None and hard.exists()
    # cherry-mx-blue has no dedicated space sample; falls back to generic
    space = pack.pick("space", "mid")
    assert space is not None and space.exists()
    cream = load_pack("nk-cream")
    assert cream.pick("space", "mid") is not None
    assert cream.pick("enter", "hard") is not None


def test_state_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = AppState(volume=0.55, pack="cherry-mx-blue", sensitivity=1.3)
    save_state(s, path)
    loaded = load_state(path)
    assert loaded.volume == 0.55
    assert loaded.pack == "cherry-mx-blue"
    assert loaded.sensitivity == 1.3
