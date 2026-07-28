"""Sound pack loader (Mechvibes-compatible + layered soft/mid/hard)."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .paths import default_packs_dir

log = logging.getLogger("mcl_kboard.pack")

KEY_ALIASES: Dict[str, str] = {
    "space": "space",
    "enter": "enter",
    "return": "enter",
    "backspace": "backspace",
    "tab": "tab",
    "esc": "esc",
    "escape": "esc",
}

STYLE_LABELS = {
    "clicky": "Clicky 青轴系",
    "linear": "Linear 线性",
    "tactile": "Tactile 段落",
    "typewriter": "莫尔斯电报 滴滴滴",
    "buckling-spring": "折叠弹簧",
    "mechanical": "机械键盘",
}


@dataclass
class PackInfo:
    id: str
    display_name: str
    style: str = ""
    description: str = ""

    @property
    def label(self) -> str:
        style = STYLE_LABELS.get(self.style, self.style)
        if style:
            return f"{self.display_name}  [{style}]"
        return self.display_name


@dataclass
class SoundPack:
    name: str
    root: Path
    layered: Dict[str, Dict[str, List[Path]]] = field(default_factory=dict)
    flat: Dict[str, List[Path]] = field(default_factory=dict)
    default_key: str = "generic"
    display_name: str = ""
    style: str = ""
    description: str = ""

    def has_layers(self) -> bool:
        return bool(self.layered)

    def pick(self, key_id: str, layer: str = "mid") -> Optional[Path]:
        key_id = KEY_ALIASES.get(key_id.lower(), key_id.lower())
        if self.layered:
            layer_map = self.layered.get(layer) or self.layered.get("mid") or {}
            paths = layer_map.get(key_id) or layer_map.get(self.default_key)
            if not paths and layer != "mid":
                mid = self.layered.get("mid") or {}
                paths = mid.get(key_id) or mid.get(self.default_key)
            if paths:
                return random.choice(paths)
        paths = self.flat.get(key_id) or self.flat.get(self.default_key)
        if paths:
            return random.choice(paths)
        return None


def list_packs(packs_dir: Optional[Path] = None) -> List[str]:
    return [p.id for p in list_pack_infos(packs_dir)]


def list_pack_infos(packs_dir: Optional[Path] = None) -> List[PackInfo]:
    root = packs_dir or default_packs_dir()
    catalog_path = root / "catalog.json"
    catalog_by_id: Dict[str, dict] = {}
    if catalog_path.exists():
        try:
            for row in json.loads(catalog_path.read_text(encoding="utf-8")):
                catalog_by_id[row["id"]] = row
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    infos: List[PackInfo] = []
    if not root.is_dir():
        return infos
    for p in sorted(root.iterdir()):
        if not p.is_dir() or not (p / "config.json").exists():
            continue
        cfg: dict = {}
        try:
            cfg = json.loads((p / "config.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        cat = catalog_by_id.get(p.name, {})
        infos.append(
            PackInfo(
                id=p.name,
                display_name=cfg.get("display_name") or cat.get("display_name") or p.name,
                style=cfg.get("style") or cat.get("style") or "",
                description=cfg.get("description") or cat.get("description") or "",
            )
        )
    return infos


def resolve_pack_id(name_or_alias: str, packs_dir: Optional[Path] = None) -> str:
    """Resolve pack id from id, display_name, or style alias."""
    key = name_or_alias.strip().lower()
    infos = list_pack_infos(packs_dir)
    for info in infos:
        if info.id.lower() == key:
            return info.id
    for info in infos:
        if info.display_name.lower() == key:
            return info.id
    # style shortcut: typewriter / clicky / linear ...
    style_matches = [i for i in infos if i.style.lower() == key]
    if len(style_matches) == 1:
        return style_matches[0].id
    if key in ("打字机", "电报机", "typewriter"):
        for info in infos:
            if info.style == "typewriter" or info.id == "typewriter":
                return info.id
    raise FileNotFoundError(f"未找到音色包: {name_or_alias}")


def load_pack(name: str, packs_dir: Optional[Path] = None) -> SoundPack:
    try:
        name = resolve_pack_id(name, packs_dir)
    except FileNotFoundError:
        pass
    root = (packs_dir or default_packs_dir()) / name
    cfg_path = root / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Sound pack not found: {root}")

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    pack = SoundPack(
        name=name,
        root=root,
        default_key=cfg.get("default", "generic"),
        display_name=cfg.get("display_name", name),
        style=cfg.get("style", ""),
        description=cfg.get("description", ""),
    )

    layers = cfg.get("layers")
    if isinstance(layers, dict):
        for layer_name, mapping in layers.items():
            pack.layered[layer_name] = {}
            if not isinstance(mapping, dict):
                continue
            for key_id, files in mapping.items():
                paths = _resolve_files(root, files)
                if paths:
                    pack.layered[layer_name][str(key_id)] = paths
        return pack

    defines = cfg.get("defines") or cfg.get("sounds") or cfg.get("keys") or {}
    if isinstance(defines, dict):
        for key_id, files in defines.items():
            kid = str(key_id)
            if kid.isdigit():
                continue
            paths = _resolve_files(root, files)
            if paths:
                pack.flat[kid.lower()] = paths

    for layer in ("soft", "mid", "hard"):
        d = root / layer
        if d.is_dir():
            pack.layered.setdefault(layer, {})
            for wav in sorted(d.glob("*.wav")):
                pack.layered[layer].setdefault(wav.stem.lower(), []).append(wav)
            if "generic" not in pack.layered[layer]:
                all_wavs = sorted(d.glob("*.wav"))
                if all_wavs:
                    pack.layered[layer]["generic"] = all_wavs

    if not pack.flat and not pack.layered:
        wavs = sorted(root.rglob("*.wav"))
        if wavs:
            pack.flat["generic"] = wavs

    return pack


def _resolve_files(root: Path, files: object) -> List[Path]:
    if files is None:
        return []
    if isinstance(files, str):
        files = [files]
    if not isinstance(files, list):
        return []
    out: List[Path] = []
    for f in files:
        p = root / str(f)
        if p.exists():
            out.append(p)
        else:
            ap = Path(str(f))
            if ap.exists():
                out.append(ap)
    return out
