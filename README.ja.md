<p align="center">
  <img src="src/mcl_kboard/assets/icon-preview.png" width="144" alt="mcl-kboard アイコン">
</p>

<h1 align="center">mcl-kboard</h1>

<p align="center">
  <a href="README.en.md">English</a> ·
  <a href="README.md">简体中文</a> ·
  日本語 ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  Apple Silicon MacBook の内蔵モーションセンサーを使い、静かなノートブックキーボードにメカニカルキーボードの打鍵音を加え、強弱に応じて音を変化させます。
</p>

<p align="center">
  <a href="https://github.com/xiehongfei/mcl-kboard">GitHub</a> ·
  <a href="https://gitee.com/hongfeieleven/mcl-kboard">Gitee</a>
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-black?logo=apple">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-Apple%20Silicon-black">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/code%20license-MIT-green">
</p>

<p align="center">
  <img src="docs/images/menubar.png" width="360" alt="メニューバー：音効・音量・音色・感度">
</p>

> [!WARNING]
> 実験的プロジェクトです。非公開の macOS センサー API に依存するため、システム更新で動かなくなる可能性があります。実力度の検出には対応した Apple Silicon MacBook が必要です。

## 2 つの使い方

| | 日常利用 | 開発 / デバッグ |
|--|----------|----------------|
| 目的 | 実力度に応じた打鍵音 | キー・音声・メニューバーの確認 |
| sudo | 初回インストールのみ | 不要 |
| 力の取得元 | 本体加速度センサー | `imu --mock`（デモ用） |
| 日常コマンド | `start` / `stop` | 2 ターミナル + mock |

多くのユーザーは **[日常利用](#日常利用)** だけで十分です。

---

## 日常利用

### 1. 初回インストール（一度だけ）

```bash
# GitHub
git clone https://github.com/xiehongfei/mcl-kboard.git
# または Gitee
# git clone https://gitee.com/hongfeieleven/mcl-kboard.git

cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash packaging/install.sh     # 管理者パスワードを求められます
mcl-kboard doctor --reveal    # 「アクセシビリティ」を有効化
```

`install.sh` の内容：

- `/usr/local/mcl-kboard` へインストール
- `/usr/local/bin/mcl-kboard` を作成
- バックグラウンド IMU デーモンを起動（ログイン時起動）

> `sudo mcl-kboard install` は使わないでください（PATH が消えます）。上記か次を使います：
> `sudo "$(pwd)/.venv/bin/mcl-kboard" install`

**アクセシビリティ**（必須。未許可だと無音）：

1. システム設定 → プライバシーとセキュリティ → アクセシビリティ
2. `doctor` が表示する Python.app を追加して有効化
3. ターミナル / 使用中の IDE も許可推奨

### 2. 毎日の操作

インストール後は任意のターミナルで：

```bash
mcl-kboard start --menubar    # 開始
mcl-kboard stop               # 停止
mcl-kboard status             # 状態
```

メニューバーに**馬のアイコン**が出ます。クリックすると：

- 音効のオン / オフ
- 音量調整
- 音色切替（切替後に 3 音プレビュー）
- 感度調整
- 試聴 / 終了

CLI のみでも可：

```bash
mcl-kboard volume 80
mcl-kboard style cherry-mx-blue
mcl-kboard style typewriter
```

### 3. アンインストール

```bash
mcl-kboard stop --full
sudo /usr/local/bin/mcl-kboard uninstall
```

設定は `~/Library/Application Support/mcl-kboard/` に残ります。不要なら手動削除してください。

---

## 開発 / デバッグ

コード変更や音声経路の確認用。**実力度は出ません。** sudo 不要。

```bash
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

ターミナルを 2 つ：

```bash
# A: 模擬加速度計
mcl-kboard imu --mock

# B: 再生 + メニューバー
mcl-kboard start --menubar --test-sound
```

テスト：

```bash
pytest
```

---

## 内蔵音色

| id | 説明 |
|----|------|
| `cherry-mx-blue` | Cherry MX Blue（Clicky） |
| `turquoise` | Kailh Box Jade（Clicky） |
| `nk-cream` | NovelKeys Cream（Linear） |
| `holy-panda` | Holy Panda（Tactile） |
| `ibm-model-m` | IBM Model M バックスプリング |
| `typewriter` | モールス電信の「ピッピッ」（タイプライター打鍵ではない） |

出典とライセンス：[`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md)

---

## 互換性

必要：Apple Silicon MacBook（主に M2+）、macOS、Python 3.9+、アクセシビリティ権限。

非対応：Intel Mac、該当センサーのないデスクトップ、外付けキーボード主体の環境。

センサーは [`macimu`](https://github.com/olvvier/apple-silicon-accelerometer) 経由です。

```bash
ioreg -l -w0 | grep -A5 AppleSPUHIDDevice
```

---

## 仕組み

```text
本体 IMU（約 200 Hz）
        │
        ▼
  IMU デーモン（root / mock）
        │  Unix socket で衝撃振幅を配信
        ▼
  ユーザーエージェント（キー監視）
        │  力を soft/mid/hard + 音量へ
        ▼
     スピーカー
```

---

## コマンド早見表

| コマンド | 内容 |
|----------|------|
| `mcl-kboard start --menubar` | 音効 + メニューバー開始 |
| `mcl-kboard stop` | 停止 |
| `mcl-kboard status` | 状態表示 |
| `mcl-kboard volume 80` | 音量 80%（`+` / `-` 可） |
| `mcl-kboard style <name>` | 音色切替 |
| `mcl-kboard doctor` | 診断 |
| `mcl-kboard imu --mock` | 模擬 IMU（開発） |

詳細は `mcl-kboard <command> --help`。

---

## トラブルシュート

| 症状 | 対処 |
|------|------|
| テスト音は鳴るが打鍵が無音 | `doctor --reveal` 後、`stop` → `start --menubar` |
| 音はあるが強弱がない | mock で実力度は測れない。`status` で `imu daemon: loaded` を確認 |
| 馬アイコンがない | `mcl-kboard menubar` |
| `sudo: mcl-kboard: command not found` | `bash packaging/install.sh` を使う |

---

## プライバシー

キー・力・音声はすべて端末内処理。テレメトリなし。ログ：`~/Library/Application Support/mcl-kboard/`。

---

## ライセンス

コード：[MIT License](LICENSE)。

`packs/` には第三者音声が含まれます。IBM Model M は [`bucklespring`](https://github.com/zevv/bucklespring)（GPL-2.0）。詳細は [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md)。
