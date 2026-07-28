<p align="center">
  <img src="src/mcl_kboard/assets/icon-preview.png" width="144" alt="Icône mcl-kboard">
</p>

<h1 align="center">mcl-kboard</h1>

<p align="center">
  <a href="README.en.md">English</a> ·
  <a href="README.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  Français ·
  <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  Utilise le capteur de mouvement intégré des MacBook Apple Silicon pour ajouter des sons de clavier mécanique au clavier silencieux de l’ordinateur, avec une intensité qui suit la force de frappe.
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS-black?logo=apple">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-Apple%20Silicon-black">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/code%20license-MIT-green">
</p>

<p align="center">
  <img src="docs/images/menubar.png" width="360" alt="Barre de menus : sons, volume, packs et sensibilité">
</p>

> [!WARNING]
> Projet expérimental. Il dépend d’interfaces capteur macOS non documentées et peut casser après une mise à jour système. La détection réelle de la force nécessite un MacBook Apple Silicon compatible.

## Deux modes d’usage

| | Usage quotidien | Développement / debug |
|--|-----------------|------------------------|
| Objectif | Sons réactifs à la force de frappe | Vérifier touches, audio, barre de menus |
| sudo | Une seule fois à l’installation | Non |
| Source de force | Accéléromètre intégré | `imu --mock`（démo seulement） |
| Commandes | `start` / `stop` | Deux terminaux + mock |

La plupart des utilisateurs n’ont besoin que de **[Usage quotidien](#usage-quotidien)**.

---

## Usage quotidien

### 1. Installation unique

```bash
git clone https://github.com/xiehongfei/mcl-kboard.git
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash packaging/install.sh     # demande le mot de passe admin
mcl-kboard doctor --reveal    # activer l’Accessibilité
```

`install.sh` :

- Installe dans `/usr/local/mcl-kboard`
- Crée `/usr/local/bin/mcl-kboard`
- Démarre le démon IMU（au login）

> N’utilisez pas `sudo mcl-kboard install`（PATH effacé）. Préférez la commande ci-dessus, ou :
> `sudo "$(pwd)/.venv/bin/mcl-kboard" install`

**Accessibilité**（obligatoire, sinon silence）:

1. Réglages Système → Confidentialité et sécurité → Accessibilité
2. Ajoutez le Python.app indiqué par `doctor` et activez-le
3. Autorisez aussi Terminal ou votre IDE

### 2. Au quotidien

Après installation, dans n’importe quel terminal :

```bash
mcl-kboard start --menubar    # démarrer
mcl-kboard stop               # arrêter
mcl-kboard status             # état
```

Une **icône de cheval** apparaît dans la barre de menus. Cliquez pour :

- Activer / désactiver les sons
- Régler le volume
- Changer de pack（aperçu de 3 sons）
- Régler la sensibilité
- Préécouter / quitter

Ou via la CLI :

```bash
mcl-kboard volume 80
mcl-kboard style cherry-mx-blue
mcl-kboard style typewriter
```

### 3. Désinstallation

```bash
mcl-kboard stop --full
sudo /usr/local/bin/mcl-kboard uninstall
```

Les préférences restent dans `~/Library/Application Support/mcl-kboard/`.

---

## Développement / debug

Pour modifier le code et tester l’audio. **Pas de vraie force.** Pas de sudo.

```bash
cd mcl-kboard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Deux terminaux :

```bash
# A : accéléromètre simulé
mcl-kboard imu --mock

# B : lecture + barre de menus
mcl-kboard start --menubar --test-sound
```

```bash
pytest
```

---

## Packs intégrés

| id | Description |
|----|-------------|
| `cherry-mx-blue` | Cherry MX Blue（Clicky） |
| `turquoise` | Kailh Box Jade（Clicky） |
| `nk-cream` | NovelKeys Cream（Linear） |
| `holy-panda` | Holy Panda（Tactile） |
| `ibm-model-m` | IBM Model M（buckling spring） |
| `typewriter` | Télégraphe Morse「di-di」（pas une machine à écrire） |

Sources et licences : [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).

---

## Compatibilité

Requis : MacBook Apple Silicon（souvent M2+）, macOS, Python 3.9+, permission Accessibilité.

Non pris en charge : Mac Intel, bureaux sans le capteur, clavier externe comme entrée principale.

Accès capteur via [`macimu`](https://github.com/olvvier/apple-silicon-accelerometer).

```bash
ioreg -l -w0 | grep -A5 AppleSPUHIDDevice
```

---

## Fonctionnement

```text
IMU portable（~200 Hz）
        │
        ▼
  Démon IMU（root / mock）
        │  Socket Unix（amplitude d’impact）
        ▼
  Agent utilisateur（touches）
        │  Force → soft/mid/hard + volume
        ▼
     Haut-parleurs
```

---

## Aide-mémoire

| Commande | Action |
|----------|--------|
| `mcl-kboard start --menubar` | Démarrer sons + barre de menus |
| `mcl-kboard stop` | Arrêter |
| `mcl-kboard status` | État |
| `mcl-kboard volume 80` | Volume 80 %（aussi `+` / `-`） |
| `mcl-kboard style <name>` | Changer de pack |
| `mcl-kboard doctor` | Diagnostic |
| `mcl-kboard imu --mock` | IMU simulé（dev） |

Options : `mcl-kboard <command> --help`.

---

## Dépannage

| Symptôme | Solution |
|----------|----------|
| Son test OK, frappe silencieuse | `doctor --reveal`, puis `stop` et `start --menubar` |
| Son sans nuance de force | Ne pas utiliser mock pour la vraie force ; vérifier `imu daemon: loaded` |
| Pas d’icône cheval | `mcl-kboard menubar` |
| `sudo: mcl-kboard: command not found` | Utiliser `bash packaging/install.sh` |

---

## Confidentialité

Frappe, force et audio restent sur l’appareil. Pas de télémétrie. Logs : `~/Library/Application Support/mcl-kboard/`.

---

## Licence

Code : [MIT License](LICENSE).

`packs/` contient des audios tiers ; échantillons IBM Model M issus de [`bucklespring`](https://github.com/zevv/bucklespring)（GPL-2.0）. Voir [`packs/THIRD-PARTY-LICENSES.md`](packs/THIRD-PARTY-LICENSES.md).
