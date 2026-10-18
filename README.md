# 游戏脚本中心 · GameHub Lite v0.3.0

一个 Windows 桌面启动器：把 **明日方舟（MAA）**、**异环（MaaNTE）**、
**鸣潮（ok-ww）**、**明日方舟终末地（MaaEnd）** 四个游戏脚本软件收进同一个窗口。

一键启动、实时运行状态、版本检查与更新入口、官网 / GitHub 直达、Clash Verge 快捷打开，
并且**自动识别脚本路径**，整个文件夹搬到别的电脑 / 别的盘符也能直接用。

![界面预览](docs/screenshot.png)

## 功能

| 功能 | 说明 |
| --- | --- |
| 一键启动 | 点卡片或「启动」按钮拉起脚本；已在运行则把它的窗口切到最前 |
| 运行状态 | 每 1.5 秒检测进程，显示 ● 未启动 / ● 运行中 / ● 启动中；退出后自动复位 |
| 版本检查 | 后台检查最新版本，有新版本时显示 `MAA · v6.19.0 → v6.20.0` 并高亮「更新」 |
| 更新 | 点「更新」打开对应脚本，让它走自己的更新流程（脚本自更新最安全） |
| 官网 / GitHub | 每张卡片底部一键打开对应项目主页与仓库 |
| Clash Verge | 右上角按钮一键打开 / 切到 Clash Verge，方便访问 GitHub |
| 路径自动识别 | 配置优先 → 自动扫描脚本目录 → 预期位置，找不到时可手动选择 |
| 可移植 | 路径以相对路径保存；换电脑、换盘符、脚本升级换目录名后仍能自动找到 |
| 深色界面 | Win11 深色标题栏，纯 tkinter + PNG 素材，运行时不需要第三方库 |

## 快速开始

1. 安装 [Python 3.10+](https://www.python.org/downloads/windows/)（安装时勾选
   **Add python.exe to PATH**）。
2. 把本仓库解压到脚本软件所在目录的旁边，例如：

```
D:\All MAA\
├─ GameHub\                ← 本程序（仓库根目录）
├─ MAA-v6.19.0-win-x64\    ← 明日方舟 MAA
├─ MaaNTE\                 ← 异环 MaaNTE
├─ WuwaMAA\ok-ww\          ← 鸣潮 ok-ww
└─ MaaEnd-win-x86_64-v2.33.0\  ← 明日方舟终末地 MaaEnd
```

3. 双击 `启动游戏中心.bat` 启动。
4. 想要桌面图标：双击 `创建桌面快捷方式.bat`。

> 脚本目录名不需要固定：Hub 会在自己所在目录里按 exe 文件名自动查找
> `MAA.exe` / `MaaNTE.exe` / `ok-ww.exe` / `MaaEnd.exe`，版本号目录名变了也能找到。
> 如果脚本放在别处，可以在 `config.json` 里设置 `"root": "D:/其他/脚本目录"`。

### 打包成免 Python 的单文件 exe（可选）

在装有 Python 的机器上双击 `tools\build_exe.bat`，会生成
`dist\GameHub.exe`；把它复制到 `GameHub\` 文件夹里，之后双击 `启动游戏中心.bat`
会优先运行它（不需要安装 Python）。

## 使用

- 鼠标悬停卡片：整张卡片高亮，底部链接变亮。
- 点卡片 / `启动` 按钮：启动脚本；运行中再点 = 切到前台。
- 卡片底部：`更新` `官网` `GitHub` `文件夹`。
- 右上角：`重新识别路径`（脚本换了位置/升级后点一下）、`打开 Clash Verge`。
- 快捷键：`1` `2` `3` `4` 启动对应脚本，`F5` 检查更新 + 刷新，`Esc` 退出。
- 重复打开不会开第二个窗口，只会把已开的窗口提到前面。

### 更新是怎么做的

Hub 只负责**检查和提醒**，真正的文件更新由脚本自己完成：

- MAA：启动时会检查更新并提示；
- MaaNTE / MaaEnd：启动后自动检查更新；
- ok-wo：启动即自动更新。

点「更新」时，如果检测到新版本会提示目标版本并打开脚本；已是最新则提示
`已是最新版本 vX`；脚本正在运行时提示先在它自己的窗口里完成更新。

版本号来源：MAA 读 `MAA.exe` 文件版本，MaaNTE / MaaEnd 读 `interface.json`，
ok-ww 读 `data\apps\ok-ww\app.json`；最新版本来自 MAA 官方 API 与 GitHub Releases。

### 路径与配置

程序会生成 `config.json`（已在 .gitignore 中忽略）：

```json
{
  "version": 2,
  "apps": {
    "maa": "MAA-v6.19.0-win-x64/MAA.exe",
    "nte": "MaaNTE/MaaNTE.exe",
    "wuwa": "WuwaMAA/ok-ww/ok-ww.exe",
    "maaend": "MaaEnd-win-x86_64-v2.33.0/MaaEnd.exe"
  },
  "clash": "C:/Program Files/Clash Verge/clash-verge.exe",
  "root": "可选：脚本所在目录（默认是 Hub 的上一级目录）"
}
```

- 路径优先保存为相对路径，因此整个文件夹搬走后依然有效；
- 手动选择过路径会记住，点「重新识别路径」可重新扫描；
- `root` 可指向任意脚本目录（使用绝对路径），适合 Hub 与脚本分开放置。

## 目录结构

```
GameHub/
├─ hub.pyw                 主程序（tkinter，无第三方依赖）
├─ assets/                 界面素材（背景、按钮、图标）— 运行时需要
│  ├─ bg_home.png / bg_hover_0..3.png
│  ├─ button_<i>_normal|hover|off.png
│  ├─ clash_*.png / rescan_*.png / dot_*.png / hub.ico|png
│  └─ maa.png / nte.png / wuwa.png / maaend.png
├─ tools/                  开发工具（运行时不需要）
│  ├─ build_assets.py      重新生成 assets 素材（需要 Pillow）
│  ├─ extract_icons.py     从本地脚本提取图标
│  ├─ build_exe.bat        PyInstaller 打包成单文件 exe
│  ├─ create_shortcut.ps1  创建桌面快捷方式（由根目录 bat 调用）
│  ├─ test_update.py       单独测试更新检查
│  ├─ grab_hub.py          后台截取 Hub 窗口（调试用）
│  └─ preview.py           截图工具（调试用）
├─ docs/screenshot.png     界面截图
├─ 启动游戏中心.bat
├─ 创建桌面快捷方式.bat
├─ README.md / CHANGELOG.md / LICENSE / .gitignore
```

## 二次开发

### 改配色 / 布局

编辑 `tools/build_assets.py` 顶部的尺寸与颜色常量（`W/H`、`CARD_X`、`ACCENTS`、
`GAMES` 等），然后：

```bash
pip install pillow
python tools/build_assets.py
```

### 增加一个脚本

1. `tools/build_assets.py` 的 `GAMES` / `ACCENTS` 中加一项并重新生成素材；
2. `hub.pyw` 顶部 `CARD_X` 加一个位置、`APPS` 加一项（`exe_name`、`procs`、
   官网/GitHub/release 链接）；
3. `tools/extract_icons.py` 的 `TARGETS` 加上图标来源。

### 换图标

`assets/*.png` 是 256×256 透明背景图标，可直接替换。仓库里的图标来自各脚本软件
本身（从 exe 提取 / 官方 logo），仅作为本机启动器的展示素材；如果你要公开分发，
建议换成自己的图标或占位图。

## 常见问题

**Q: 提示“路径缺失”？**
点卡片按提示选择该脚本的 exe；或先确认脚本已解压到 Hub 所在目录，再点右上角
「重新识别路径」。选过一次后会写入 `config.json`。

**Q: 更新检查显示“无法检查”？**
GitHub / 官方 API 需要网络访问；点右上角打开 Clash Verge 后按 `F5` 重试。
MaaNTE 官方 GitHub 仓库目前在部分网络下不可访问，此时 Hub 会改为直接打开
MaaNTE 让它自行检查更新。

**Q: 提示需要管理员权限？**
`ok-ww` 自身要求管理员权限，Hub 会自动以管理员方式拉起（可能弹 UAC，点「是」）。

**Q: 支持其他游戏脚本吗？**
可以，参考上面「增加一个脚本」，界面是数据驱动的；后续也可以做成配置文件驱动。

## 许可证

本仓库代码使用 MIT License。各脚本软件（MAA / MaaNTE / ok-ww / MaaEnd）及其图标
版权归各自作者所有，本仓库不包含它们的程序文件，也不对其行为负责。
