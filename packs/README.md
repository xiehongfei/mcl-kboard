# 音色包 / 声源风格

灵感参考：[kbs.im](https://kbs.im/) · [keyboardsimulator.xyz](https://keyboardsimulator.xyz/) ·
[clickandthock](https://www.clickandthock.com/) ·
[Listening Museum](https://sheets.works/data-viz/keyboard-sounds) ·
[keysim](https://github.com/crsnbrt/keysim)

许可与来源见 [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)。

## 支持的音色列表

| id | 显示名 | 类型 | 说明 |
|----|--------|------|------|
| `cherry-mx-blue` | Cherry MX 青轴 | Clicky | 青轴 clicky 真实录音（Mechvibes） |
| `turquoise` | Kailh Box 青绿 | Clicky | Box Turquoise 真实录音（Mechvibes） |
| `nk-cream` | NovelKeys 奶油轴 | Linear | 奶油轴线性真实录音（Mechvibes） |
| `holy-panda` | Holy Panda | Tactile | 熊猫轴段落感真实录音（kbsim / Mechvibes） |
| `ibm-model-m` | IBM Model M | 折叠弹簧 | buckling spring（bucklespring，GPL-2.0） |
| `typewriter` | 电报机（莫尔斯滴滴） | 莫尔斯电报 | 谍片风格「滴滴滴」边音，**不是**打字机敲击声 |

## 切换方式

### 命令行

```bash
mcl-kboard style                 # 列出（当前项前有 *）
mcl-kboard packs                 # 同上

mcl-kboard style typewriter      # 电报机「滴滴滴」
mcl-kboard style 电报机          # 别名
mcl-kboard style cherry-mx-blue
mcl-kboard style turquoise
mcl-kboard style nk-cream
mcl-kboard style holy-panda
mcl-kboard style ibm-model-m

mcl-kboard set --pack nk-cream   # 等价
mcl-kboard status                # 查看当前 pack / style
```

支持用 **id**、**显示名** 或别名（如 `电报机`）切换。运行中的 agent 会读 `state.json` 热加载；未生效时：

```bash
mcl-kboard stop && mcl-kboard start
```

### 菜单栏

```bash
mcl-kboard start --menubar
```

**声源风格** → 点选；**试听当前音色** 可预听。

## 重新生成 / 拉取

```bash
python scripts/fetch_real_packs.py      # 机械轴等开源录音
python scripts/generate_telegraph.py    # 莫尔斯「滴滴滴」
```

## 自定义音色包格式

```
packs/我的音色包/
  config.json
  sounds/*.wav
```

```json
{
  "default": "generic",
  "display_name": "我的音色",
  "style": "custom",
  "layers": {
    "soft": { "generic": ["sounds/a.wav"] },
    "mid":  { "generic": ["sounds/a.wav", "sounds/b.wav"] },
    "hard": { "generic": ["sounds/b.wav"] }
  }
}
```
