<p align="center">
  <img src="src/mcl_kboard/assets/icon-preview.png" width="144" alt="mcl-kboard 아이콘">
</p>

<h1 align="center">mcl-kboard</h1>

<p align="center">
  <a href="README.en.md">English</a> ·
  <a href="README.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  한국어 ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  Apple Silicon MacBook 내장 모션 센서로 조용한 노트북 키보드에 기계식 키보드 타건음을 더하고, 누르는 힘에 따라 소리가 달라지게 합니다.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-black?logo=apple">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-Apple%20Silicon-black">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/code%20license-MIT-green">
</p>

<p align="center">
  <img src="docs/images/menubar.png" width="360" alt="메뉴 막대: 사운드, 볼륨, 팩, 감도">
</p>

> [!WARNING]
> 실험적 프로젝트입니다. 문서화되지 않은 macOS 센서 인터페이스에 의존하므로 시스템 업데이트 후 동작하지 않을 수 있습니다. 실제 타건 강도 감지에는 호환되는 Apple Silicon MacBook이 필요합니다.

## 두 가지 사용 방식

| | 일상 사용 | 개발 / 디버그 |
|--|-----------|---------------|
| 목적 | 실제 강도에 따른 타건음 | 키·오디오·메뉴 막대 검증 |
| sudo | 최초 설치 한 번만 | 불필요 |
| 강도 소스 | 본체 가속도계 | `imu --mock`（데모） |
| 일상 명령 | `start` / `stop` | 터미널 2개 + mock |

대부분 사용자는 **[일상 사용](#일상-사용)** 만 보면 됩니다.

---

## 일상 사용

### 1. 최초 설치（한 번만）

```bash
git clone https://github.com/xiehongfei/mcl-kboard.git
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash packaging/install.sh     # 관리자 암호 입력
mcl-kboard doctor --reveal    # 손쉬운 사용 권한 허용
```

`install.sh` 가 하는 일:

- `/usr/local/mcl-kboard` 에 설치
- `/usr/local/bin/mcl-kboard` 생성
- 백그라운드 IMU 데몬 시작（로그인 시 자동）

> `sudo mcl-kboard install` 은 사용하지 마세요（PATH가 비워집니다）. 위 명령 또는:
> `sudo "$(pwd)/.venv/bin/mcl-kboard" install`

**손쉬운 사용**（필수, 없으면 무음）:

1. 시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용
2. `doctor` 가 출력한 Python.app 추가 후 활성화
3. 터미널 / 사용 중인 IDE도 권장

### 2. 매일 쓰는 방법

설치 후 아무 터미널에서:

```bash
mcl-kboard start --menubar    # 켜기
mcl-kboard stop               # 끄기
mcl-kboard status             # 상태
```

메뉴 막대에 **말 아이콘**이 나타납니다. 클릭하면:

- 사운드 켜기 / 끄기
- 볼륨 조절
- 사운드 팩 전환（전환 후 3번 미리듣기）
- 감도 조절
- 미리듣기 / 종료

CLI만 사용해도 됩니다:

```bash
mcl-kboard volume 80
mcl-kboard style cherry-mx-blue
mcl-kboard style typewriter
```

### 3. 제거

```bash
mcl-kboard stop --full
sudo /usr/local/bin/mcl-kboard uninstall
```

설정은 `~/Library/Application Support/mcl-kboard/` 에 남습니다.

---

## 개발 / 디버그

코드 수정·오디오 경로 테스트용. **실제 강도는 없음.** sudo 불필요.

```bash
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

터미널 두 개:

```bash
# A: 모의 가속도계
mcl-kboard imu --mock

# B: 재생 + 메뉴 막대
mcl-kboard start --menubar --test-sound
```

```bash
pytest
```

---

## 내장 사운드 팩

| id | 설명 |
|----|------|
| `cherry-mx-blue` | Cherry MX Blue（Clicky） |
| `turquoise` | Kailh Box Jade（Clicky） |
| `nk-cream` | NovelKeys Cream（Linear） |
| `holy-panda` | Holy Panda（Tactile） |
| `ibm-model-m` | IBM Model M 버클링 스프링 |
| `typewriter` | 모스 전신 「띠띠」（타자기 타건 아님） |

출처·라이선스: [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md)

---

## 호환성

필요: Apple Silicon MacBook（보통 M2+）, macOS, Python 3.9+, 손쉬운 사용 권한.

비지원: Intel Mac, 해당 센서 없는 데스크톱, 외장 키보드 위주 환경.

센서 접근: [`macimu`](https://github.com/olvvier/apple-silicon-accelerometer)

```bash
ioreg -l -w0 | grep -A5 AppleSPUHIDDevice
```

---

## 동작 원리

```text
본체 IMU（약 200 Hz）
        │
        ▼
  IMU 데몬（root / mock）
        │  Unix socket 로 충격 진폭 전송
        ▼
  사용자 agent（키 감시）
        │  강도 → soft/mid/hard + 볼륨
        ▼
     스피커
```

---

## 명령 요약

| 명령 | 역할 |
|------|------|
| `mcl-kboard start --menubar` | 사운드 + 메뉴 막대 시작 |
| `mcl-kboard stop` | 중지 |
| `mcl-kboard status` | 상태 |
| `mcl-kboard volume 80` | 볼륨 80%（`+` / `-` 가능） |
| `mcl-kboard style <name>` | 팩 전환 |
| `mcl-kboard doctor` | 진단 |
| `mcl-kboard imu --mock` | 모의 IMU（개발） |

자세한 옵션: `mcl-kboard <command> --help`

---

## 문제 해결

| 증상 | 조치 |
|------|------|
| 테스트음은 나고 타이핑은 무음 | `doctor --reveal` 후 `stop` → `start --menubar` |
| 소리는 있으나 강약 없음 | mock로는 실제 강도 불가. `status` 에서 `imu daemon: loaded` 확인 |
| 말 아이콘 없음 | `mcl-kboard menubar` |
| `sudo: mcl-kboard: command not found` | `bash packaging/install.sh` 사용 |

---

## 개인정보

키·강도·오디오는 모두 기기 내 처리. 원격 전송 없음. 로그: `~/Library/Application Support/mcl-kboard/`

---

## 라이선스

코드: [MIT License](LICENSE).

`packs/` 에 서드파티 오디오 포함. IBM Model M 샘플은 [`bucklespring`](https://github.com/zevv/bucklespring)（GPL-2.0）. 자세한 내용: [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).
