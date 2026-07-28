#!/usr/bin/env python3
"""拉取开源真实键盘/打字机录音，生成本项目分层音色包。

来源参考（社区声源站与开源项目）：
  https://kbs.im/  https://keyboardsimulator.xyz/  https://www.clickandthock.com/
  https://sheets.works/data-viz/keyboard-sounds  https://github.com/crsnbrt/keysim
  实际音频：keesound / Mechvibes / bucklespring，以及本地生成的莫尔斯边音
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packs"
KEESOUND = "https://raw.githubusercontent.com/nirajrajgor/keesound/main/Samples"
BUCKLE = "https://raw.githubusercontent.com/zevv/bucklespring/master/wav"

# id -> metadata + download recipe
PACKS = {
    "cherry-mx-blue": {
        "display_name": "Cherry MX 青轴",
        "style": "clicky",
        "description": "青轴 clicky（Mechvibes mxblue-travel）",
        "source": "keesound",
        "files": [f"generic_{i}.wav" for i in range(1, 6)],
        "specials": [],
        "license": "MIT",
    },
    "nk-cream": {
        "display_name": "NovelKeys 奶油轴",
        "style": "linear",
        "description": "奶油轴 linear（Mechvibes cream-travel）",
        "source": "keesound",
        "files": [f"generic_{i}.wav" for i in range(1, 6)],
        "specials": ["space.wav", "enter.wav", "backspace.wav"],
        "license": "MIT",
    },
    "holy-panda": {
        "display_name": "Holy Panda",
        "style": "tactile",
        "description": "熊猫轴 tactile（kbsim / Mechvibes）",
        "source": "keesound",
        "files": [f"generic_{i}.wav" for i in range(1, 6)],
        "specials": ["space.wav", "enter.wav", "backspace.wav"],
        "license": "MIT",
    },
    "turquoise": {
        "display_name": "Kailh Box 青绿",
        "style": "clicky",
        "description": "Kailh Box Turquoise clicky（Mechvibes）",
        "source": "keesound",
        "files": [f"generic_{i}.wav" for i in range(1, 6)],
        "specials": ["space.wav", "enter.wav", "backspace.wav"],
        "license": "MIT",
    },
}


def download(url: str, dest: Path, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100:
        print(f"  skip existing {dest.name}")
        return
    print(f"  GET {url}")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            # Prefer curl for more reliable TLS on some networks
            if shutil.which("curl"):
                subprocess.check_call(
                    ["curl", "-fsSL", "--connect-timeout", "30", "--retry", "2", "-o", str(dest), url],
                )
                if dest.exists() and dest.stat().st_size > 0:
                    return
            req = urllib.request.Request(url, headers={"User-Agent": "mcl-kboard-fetch/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception as e:
            last_err = e
            print(f"  retry {attempt + 1}/{retries}: {e}")
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}") from last_err

def write_layered_config(
    out: Path,
    *,
    name: str,
    meta: dict,
    generics: list[str],
    specials: dict[str, list[str]],
) -> None:
    n = len(generics)
    soft = generics[: max(2, n // 2 + 1)] if generics else generics
    mid = generics
    hard = generics[max(0, n // 2 - 1) :] if generics else generics

    def layer_keys(gens: list[str]) -> dict:
        mapping = {"generic": gens}
        mapping.update(specials)
        return mapping

    cfg = {
        "name": name,
        "display_name": meta.get("display_name", name),
        "style": meta.get("style", "mechanical"),
        "description": meta.get("description", ""),
        "default": "generic",
        "source": meta.get("source_url", meta.get("source", "")),
        "license": meta.get("license", "see THIRD-PARTY-LICENSES.md"),
        "layers": {
            "soft": layer_keys(soft),
            "mid": layer_keys(mid),
            "hard": layer_keys(hard),
        },
    }
    (out / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def build_keesound(name: str, meta: dict) -> None:
    out = ROOT / name
    # Keep existing pack if complete
    if (out / "config.json").exists() and any((out / "sounds").glob("*.wav")):
        print(f"  keep existing {out}")
        # Refresh metadata in config
        generics = [f"sounds/{p.name}" for p in sorted((out / "sounds").glob("generic_*.wav"))]
        specials: dict[str, list[str]] = {}
        for key in ("space", "enter", "backspace"):
            p = out / "sounds" / f"{key}.wav"
            if p.exists():
                specials[key] = [f"sounds/{key}.wav"]
        if generics:
            write_layered_config(
                out,
                name=name,
                meta={**meta, "source_url": "https://github.com/nirajrajgor/keesound"},
                generics=generics,
                specials=specials,
            )
            return
    if out.exists():
        shutil.rmtree(out)
    sounds = out / "sounds"
    sounds.mkdir(parents=True)
    local_generics: list[str] = []
    for fname in meta["files"]:
        url = f"{KEESOUND}/{name}/down/{fname}"
        dest = sounds / fname
        download(url, dest)
        local_generics.append(f"sounds/{fname}")
    special_map: dict[str, list[str]] = {}
    for fname in meta["specials"]:
        url = f"{KEESOUND}/{name}/down/{fname}"
        dest = sounds / fname
        download(url, dest)
        special_map[Path(fname).stem] = [f"sounds/{fname}"]
    write_layered_config(
        out,
        name=name,
        meta={**meta, "source_url": "https://github.com/nirajrajgor/keesound"},
        generics=local_generics,
        specials=special_map,
    )
    print(f"wrote {out}")
def build_ibm_model_m() -> None:
    """IBM Model M 折叠弹簧：bucklespring (GPL-2.0)。"""
    name = "ibm-model-m"
    meta = {
        "display_name": "IBM Model M",
        "style": "buckling-spring",
        "description": "折叠弹簧 buckling spring（bucklespring）",
        "source_url": "https://github.com/zevv/bucklespring",
        "license": "GPL-2.0 (bucklespring wav)",
    }
    out = ROOT / name
    if (out / "config.json").exists() and any((out / "sounds").glob("*.wav")):
        print(f"  keep existing {out}")
        return
    if out.exists():
        shutil.rmtree(out)
    sounds = out / "sounds"
    sounds.mkdir(parents=True)
    generics: list[str] = []
    for i in range(1, 13):
        fname = f"{i:02d}-0.wav"
        url = f"{BUCKLE}/{fname}"
        dest = sounds / fname
        try:
            download(url, dest)
            generics.append(f"sounds/{fname}")
        except Exception as e:
            print(f"  skip {fname}: {e}")
    if not generics:
        raise RuntimeError("failed to download bucklespring samples")
    specials = {
        "space": [generics[min(5, len(generics) - 1)]],
        "enter": [generics[min(8, len(generics) - 1)]],
        "backspace": [generics[min(2, len(generics) - 1)]],
    }
    write_layered_config(out, name=name, meta=meta, generics=generics, specials=specials)
    print(f"wrote {out}")


def write_catalog_and_licenses() -> None:
    catalog = []
    for p in sorted(ROOT.iterdir()):
        if not p.is_dir() or not (p / "config.json").exists():
            continue
        cfg = json.loads((p / "config.json").read_text(encoding="utf-8"))
        catalog.append(
            {
                "id": p.name,
                "display_name": cfg.get("display_name", p.name),
                "style": cfg.get("style", ""),
                "description": cfg.get("description", ""),
            }
        )
    (ROOT / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    text = """# 音频来源与许可

本目录同时包含第三方键盘录音和由本项目程序化生成的音频。它们的许可独立于仓库根目录中的项目代码许可。

灵感与同类产品参考：
[kbs.im](https://kbs.im/) · [keyboardsimulator.xyz](https://keyboardsimulator.xyz/) ·
[clickandthock](https://www.clickandthock.com/) ·
[sheets.works Listening Museum](https://sheets.works/data-viz/keyboard-sounds) ·
[keysim](https://github.com/crsnbrt/keysim)

| 音色包 | 显示名 | 风格 | 来源 | 许可 |
|--------|--------|------|------|------|
| `cherry-mx-blue` | Cherry MX 青轴 | clicky | [keesound](https://github.com/nirajrajgor/keesound) ← Mechvibes | MIT |
| `nk-cream` | NovelKeys 奶油轴 | linear | keesound ← Mechvibes | MIT |
| `holy-panda` | Holy Panda | tactile | keesound ← kbsim / Mechvibes | MIT |
| `turquoise` | Kailh Box 青绿 | clicky | keesound ← Mechvibes | MIT |
| `typewriter` | 电报机（莫尔斯滴滴） | typewriter | 本地生成 CW 边音「滴滴滴」 | MIT |
| `ibm-model-m` | IBM Model M | buckling-spring | [bucklespring](https://github.com/zevv/bucklespring) | GPL-2.0 |

## 许可文件

- keesound / Mechvibes 音频：[`licenses/keesound-MIT.txt`](licenses/keesound-MIT.txt)
- bucklespring 音频：[`licenses/GPL-2.0.txt`](licenses/GPL-2.0.txt)
- `typewriter`：由 `scripts/generate_telegraph.py` 生成，随本项目代码按 MIT 许可发布

重新拉取：

```bash
python scripts/fetch_real_packs.py
```
"""
    (ROOT / "THIRD-PARTY-LICENSES.md").write_text(text, encoding="utf-8")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, meta in PACKS.items():
        print(f"=== {name} ===")
        build_keesound(name, meta)
    print("=== typewriter (Morse 滴滴滴) ===")
    import sys

    subprocess.check_call([sys.executable, str(Path(__file__).with_name("generate_telegraph.py"))])
    # print("=== ibm-model-m ===")
    # build_ibm_model_m()  # keep separate; still available
    print("=== ibm-model-m ===")
    build_ibm_model_m()
    write_catalog_and_licenses()
    print("done. packs:", ", ".join(sorted(p.name for p in ROOT.iterdir() if (p / "config.json").exists())))


if __name__ == "__main__":
    main()
