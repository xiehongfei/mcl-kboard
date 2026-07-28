# 音频来源与许可

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
