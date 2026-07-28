<p align="center">
  <img src="src/mcl_kboard/assets/icon-preview.png" width="144" alt="mcl-kboard horse icon">
</p>

<h1 align="center">mcl-kboard</h1>

<p align="center">
  English ·
  <a href="README.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  Use the built-in motion sensor on Apple Silicon MacBooks to add mechanical keyboard sounds to the otherwise quiet laptop keyboard, with volume that follows how hard you type.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-black?logo=apple">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-Apple%20Silicon-black">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/code%20license-MIT-green">
</p>

<p align="center">
  <img src="docs/images/menubar.png" width="360" alt="Menu bar: enable sounds, volume, packs, and sensitivity">
</p>

> [!WARNING]
> Experimental project. It depends on undocumented macOS sensor interfaces and may break after system updates. Real force sensing requires a compatible Apple Silicon MacBook.

## Two ways to use it

| | Daily use | Development / debug |
|--|-----------|---------------------|
| Goal | Real force-sensitive typing sounds | Verify keys, audio, and menu bar |
| Needs sudo | Only once during install | No |
| Force source | Built-in accelerometer | `imu --mock` (demo force only) |
| Daily commands | `start` / `stop` | Two terminals + mock |

Most users only need **[Daily use](#daily-use)**.

---

## Daily use

### 1. One-time install

```bash
git clone https://github.com/xiehongfei/mcl-kboard.git
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash packaging/install.sh     # prompts for admin password
mcl-kboard doctor --reveal    # enable Accessibility when prompted
```

`install.sh` will:

- Install into `/usr/local/mcl-kboard`
- Create `/usr/local/bin/mcl-kboard`
- Start the background IMU daemon (runs at login)

> Do not run `sudo mcl-kboard install` (`sudo` clears PATH). Use the command above, or:
> `sudo "$(pwd)/.venv/bin/mcl-kboard" install`

**Accessibility** (required, otherwise there is no sound):

1. System Settings → Privacy & Security → Accessibility
2. Add the Python.app path printed by `doctor` and enable it
3. Also authorize Terminal or the IDE you launch from

### 2. Everyday commands

After install, open any new terminal (no need to enter the repo):

```bash
mcl-kboard start --menubar    # on
mcl-kboard stop               # off
mcl-kboard status             # status
```

A **galloping-horse icon** appears in the menu bar. Click it to:

- Enable / disable sounds
- Adjust volume
- Switch sound packs (auto-previews three taps)
- Adjust force sensitivity
- Preview / quit

Or use the CLI only:

```bash
mcl-kboard volume 80
mcl-kboard style cherry-mx-blue
mcl-kboard style typewriter
```

### 3. Uninstall

```bash
mcl-kboard stop --full
sudo /usr/local/bin/mcl-kboard uninstall
```

User preferences stay in `~/Library/Application Support/mcl-kboard/` unless you delete them.

---

## Development / debug

For changing code and testing the audio path. **No real force sensing.** No sudo needed.

```bash
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Two terminals:

```bash
# Terminal A: mock accelerometer
mcl-kboard imu --mock

# Terminal B: playback + menu bar
mcl-kboard start --menubar --test-sound
```

Tests:

```bash
pytest
```

Optional tools:

```bash
python scripts/fetch_real_packs.py
python scripts/generate_telegraph.py
python scripts/generate_menubar_icon.py
```

---

## Built-in packs

| id | Description |
|----|-------------|
| `cherry-mx-blue` | Cherry MX Blue (Clicky) |
| `turquoise` | Kailh Box Jade (Clicky) |
| `nk-cream` | NovelKeys Cream (Linear) |
| `holy-panda` | Holy Panda (Tactile) |
| `ibm-model-m` | IBM Model M buckling spring |
| `typewriter` | Morse telegraph “dit-dit” (not typewriter strikes) |

Sources and licenses: [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).

Custom pack format: [`packs/README.md`](packs/README.md).

---

## Compatibility

Requires: Apple Silicon MacBook (typically M2+), macOS, Python 3.9+, Accessibility permission.

Not supported: Intel Macs, desktops without the sensor, external keyboards as the primary input.

Sensor access uses [`macimu`](https://github.com/olvvier/apple-silicon-accelerometer).

Hardware check:

```bash
ioreg -l -w0 | grep -A5 AppleSPUHIDDevice
```

---

## How it works

```text
Laptop IMU (~200 Hz)
        │
        ▼
  IMU daemon (root / mock)
        │  Unix socket publishes impact amplitude
        ▼
  User agent (Accessibility keydown)
        │  Align force → soft/mid/hard + volume
        ▼
     Local speakers
```

---

## Command cheat sheet

**Daily**

| Command | Action |
|---------|--------|
| `mcl-kboard start --menubar` | Start sounds + menu bar |
| `mcl-kboard stop` | Stop sounds |
| `mcl-kboard status` | Show status |
| `mcl-kboard volume 80` | Volume 80% (`+` / `-` also work) |
| `mcl-kboard style <name>` | Switch pack |
| `mcl-kboard doctor` | Diagnose permissions / sensor |

**Development**

| Command | Action |
|---------|--------|
| `mcl-kboard imu --mock` | Mock IMU |
| `mcl-kboard start --foreground` | Foreground agent (logs) |
| `mcl-kboard stop --full` | Stop sounds + IMU / menu bar |

Full options: `mcl-kboard <command> --help`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Test sound works, typing is silent | `mcl-kboard doctor --reveal`, then `stop` and `start --menubar` |
| Sound but no soft/hard difference | Do not use mock for real force; confirm `imu daemon: loaded` in `status` |
| No horse icon | `mcl-kboard menubar`; log: `~/Library/Application Support/mcl-kboard/menubar.log` |
| `sudo: mcl-kboard: command not found` | Use `bash packaging/install.sh` |

---

## Privacy

Keystrokes, force data, and audio stay on-device. No telemetry or cloud. Logs: `~/Library/Application Support/mcl-kboard/`.

---

## Project layout

```text
src/mcl_kboard/   main package
packs/            sound packs and third-party licenses
packaging/        system install script
docs/images/      screenshots
scripts/          pack / icon generators
tests/            unit tests
```

---

## Known limitations

- Depends on undocumented IOKit HID interfaces
- Force is estimated from chassis vibration, not per-key pressure sensors
- No signed `.app` / graphical installer yet

---

## License

Code: [MIT License](LICENSE).

`packs/` includes third-party audio; IBM Model M samples are from [`bucklespring`](https://github.com/zevv/bucklespring) (GPL-2.0). See [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).
