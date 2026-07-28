<p align="center">
  <img src="src/mcl_kboard/assets/icon-preview.png" width="144" alt="mcl-kboard Symbol">
</p>

<h1 align="center">mcl-kboard</h1>

<p align="center">
  <a href="README.en.md">English</a> ·
  <a href="README.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.fr.md">Français</a> ·
  Deutsch
</p>

<p align="center">
  Nutzt den integrierten Bewegungssensor von Apple-Silicon-MacBooks, um dem leisen Notebook-Keyboard mechanische Tastaturgeräusche hinzuzufügen – mit Lautstärke je nach Anschlagstärke.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-black?logo=apple">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-Apple%20Silicon-black">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/code%20license-MIT-green">
</p>

<p align="center">
  <img src="docs/images/menubar.png" width="360" alt="Menüleiste: Sounds, Lautstärke, Packs und Empfindlichkeit">
</p>

> [!WARNING]
> Experimentelles Projekt. Es hängt von undokumentierten macOS-Sensor-Schnittstellen ab und kann nach Systemupdates ausfallen. Echte Kraftmessung braucht ein kompatibles Apple-Silicon-MacBook.

## Zwei Nutzungsarten

| | Alltag | Entwicklung / Debug |
|--|--------|---------------------|
| Ziel | Echte kraftabhängige Tippsounds | Tasten, Audio und Menüleiste prüfen |
| sudo | Nur einmal bei der Installation | Nein |
| Kraftquelle | Eingebauter Beschleunigungssensor | `imu --mock`（nur Demo） |
| Befehle | `start` / `stop` | Zwei Terminals + mock |

Die meisten Nutzer brauchen nur **[Alltag](#alltag)**.

---

## Alltag

### 1. Einmalige Installation

```bash
git clone https://github.com/xiehongfei/mcl-kboard.git
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash packaging/install.sh     # Admin-Passwort
mcl-kboard doctor --reveal    # Bedienungshilfen aktivieren
```

`install.sh` :

- Installiert nach `/usr/local/mcl-kboard`
- Erstellt `/usr/local/bin/mcl-kboard`
- Startet den IMU-Daemon（beim Login）

> Nicht `sudo mcl-kboard install` verwenden（PATH wird geleert）. Stattdessen oben oder:
> `sudo "$(pwd)/.venv/bin/mcl-kboard" install`

**Bedienungshilfen**（pflichtig, sonst kein Ton）:

1. Systemeinstellungen → Datenschutz & Sicherheit → Bedienungshilfen
2. Von `doctor` angezeigtes Python.app hinzufügen und aktivieren
3. Auch Terminal / IDE freigeben

### 2. Täglicher Betrieb

Nach der Installation in jedem Terminal:

```bash
mcl-kboard start --menubar    # ein
mcl-kboard stop               # aus
mcl-kboard status             # Status
```

In der Menüleiste erscheint ein **Pferde-Symbol**. Klick für:

- Sounds ein / aus
- Lautstärke
- Soundpacks（danach 3 Vorschautöne）
- Empfindlichkeit
- Vorschau / Beenden

Oder per CLI:

```bash
mcl-kboard volume 80
mcl-kboard style cherry-mx-blue
mcl-kboard style typewriter
```

### 3. Deinstallation

```bash
mcl-kboard stop --full
sudo /usr/local/bin/mcl-kboard uninstall
```

Einstellungen bleiben in `~/Library/Application Support/mcl-kboard/`.

---

## Entwicklung / Debug

Für Code und Audiopfad. **Keine echte Kraft.** Kein sudo.

```bash
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Zwei Terminals:

```bash
# A: Mock-Beschleunigungssensor
mcl-kboard imu --mock

# B: Wiedergabe + Menüleiste
mcl-kboard start --menubar --test-sound
```

```bash
pytest
```

---

## Eingebaute Packs

| id | Beschreibung |
|----|--------------|
| `cherry-mx-blue` | Cherry MX Blue（Clicky） |
| `turquoise` | Kailh Box Jade（Clicky） |
| `nk-cream` | NovelKeys Cream（Linear） |
| `holy-panda` | Holy Panda（Tactile） |
| `ibm-model-m` | IBM Model M（Buckling Spring） |
| `typewriter` | Morse-Telegraf „di-di“（kein Schreibmaschinenanschlag） |

Quellen und Lizenzen: [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).

---

## Kompatibilität

Benötigt: Apple-Silicon-MacBook（typisch M2+）, macOS, Python 3.9+, Bedienungshilfen.

Nicht unterstützt: Intel-Macs, Desktops ohne Sensor, externe Tastatur als Haupteingabe.

Sensorzugriff über [`macimu`](https://github.com/olvvier/apple-silicon-accelerometer).

```bash
ioreg -l -w0 | grep -A5 AppleSPUHIDDevice
```

---

## Funktionsweise

```text
Laptop-IMU（~200 Hz）
        │
        ▼
  IMU-Daemon（root / mock）
        │  Unix-Socket（Stoßamplitude）
        ▼
  User-Agent（Tasten）
        │  Kraft → soft/mid/hard + Lautstärke
        ▼
     Lautsprecher
```

---

## Befehlsübersicht

| Befehl | Aktion |
|--------|--------|
| `mcl-kboard start --menubar` | Sounds + Menüleiste starten |
| `mcl-kboard stop` | Stoppen |
| `mcl-kboard status` | Status |
| `mcl-kboard volume 80` | Lautstärke 80 %（auch `+` / `-`） |
| `mcl-kboard style <name>` | Pack wechseln |
| `mcl-kboard doctor` | Diagnose |
| `mcl-kboard imu --mock` | Mock-IMU（Dev） |

Details: `mcl-kboard <command> --help`.

---

## Fehlerbehebung

| Symptom | Lösung |
|---------|--------|
| Testton ja, Tippen still | `doctor --reveal`, dann `stop` und `start --menubar` |
| Ton ohne Soft/Hard | Mock misst keine echte Kraft; in `status` `imu daemon: loaded` prüfen |
| Kein Pferde-Symbol | `mcl-kboard menubar` |
| `sudo: mcl-kboard: command not found` | `bash packaging/install.sh` verwenden |

---

## Datenschutz

Tasten, Kraft und Audio bleiben lokal. Keine Telemetrie. Logs: `~/Library/Application Support/mcl-kboard/`.

---

## Lizenz

Code: [MIT License](LICENSE).

`packs/` enthält Drittanbieter-Audio; IBM-Model-M-Samples von [`bucklespring`](https://github.com/zevv/bucklespring)（GPL-2.0）. Siehe [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).
