# Schedule Reminder

<p align="center">
  <img src="assets/icon.png" width="96" alt="Schedule Reminder icon">
</p>

一个面向 Windows 的独立桌面日历待办与提醒程序。选择日期、填写事项名称和提醒时间；到点后弹出不会自动消失的提醒窗口，可以选择“关闭提醒”或“稍后提醒”。关闭主窗口时可选择退出，或最小化到系统托盘继续接收提醒。

当前版本：**v0.3.0**（Windows x64）

## 1. 项目解决什么问题

日常待办经常散落在聊天、便签和浏览器里，普通通知又容易被忽略或自动消失。本项目把日历、待办和提醒放在一个本地桌面程序中：

- 不注册账号、不依赖网络；
- 到点提醒必须由用户明确处理；
- 所有数据保存在本机；
- 只有一个可执行文件，下载后直接运行。

这是一个独立的 Windows 桌面程序，不是网页，也不是 Agent Skill。

## 2. 主要功能

- 月历视图，支持切换上个月、下个月和回到今天。
- 点击“XXXX年XX月”标题打开月份选择面板：年份左右切换，4×3 网格选择 1–12 月。
- 点击今天或未来日期创建待办；过去日期不能新增提醒。
- 设置待办名称和提醒时间（24 小时制，支持 `9:30` 和 `09:30`）。
- 点击提醒时间输入框打开时间选择面板：小时、分钟两列滚动选择，取消不修改原值，确定才回填。
- 到点弹出置顶提醒窗口，显示事项名称和原定时间。
- 提醒弹窗没有关闭按钮、不会自动超时；`Esc` 和 `Alt+F4` 不会被用来关闭弹窗。
- 只能选择：
  - **关闭提醒**：关闭弹窗，待办作为已提醒历史保留；
  - **稍后提醒**：输入 1–1440 分钟，到点后再次提醒。
- 点击窗口右上角关闭按钮时弹出确认窗口，可选择确认关闭、最小化到系统托盘或取消关闭。
- 最小化到系统托盘后程序继续运行，到点正常提醒；托盘菜单可以重新打开主界面或退出。
- 首次启动显示应用介绍和历史更新日志；版本升级后首次启动显示本次更新日志，点击“进入应用”后保存版本记录。
- 右侧“当天待办”区分未提醒和已提醒记录；已提醒条目置灰，可手动删除任意一条。
- 默认稍后 5 分钟，并记住上次使用的分钟数。
- 多个待办同时到期时，按到期时间依次弹出处理。
- 使用本地 JSON 持久化；重新打开或重启程序后待办仍在，错过的提醒会在下次启动时补弹。
- “回到今天”仅在选中日期不是今天时显示。
- 左侧日历提供并排的月视图 / 时间线视图图标，当前视图高亮；时间线按日期分组，支持上下滚动浏览。
- 单实例运行，避免重复弹出同一批提醒。
- 内置应用图标、Windows 版本信息和 PyInstaller 打包配置。

## 3. 安装方法

### 方式一：下载 Windows 可执行文件（推荐）

从 GitHub Releases 下载：

**<https://github.com/XuBoHao-maker/schedule_reminder/releases/latest>**

下载 `ScheduleReminder.exe` 后放到任意目录，双击运行即可。无需安装 Python、无需安装额外运行库。

> 当前构建未做商业代码签名，Windows SmartScreen 可能显示“未知发布者”。确认文件来源可信后，可选择“更多信息 → 仍要运行”。正式分发建议使用代码签名证书。

### 方式二：从源码运行

要求：

- Windows 10/11 x64；
- Python 3.10+（推荐 3.12 x64，需包含 Tkinter，Windows 官方 Python 安装包默认包含）。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

运行源码需要 `pystray` 和 `Pillow` 用于系统托盘；打包依赖参考 `requirements-dev.txt`。

### 数据位置

程序数据默认保存在：

```text
%APPDATA%\ScheduleReminder\
├── todos.json
└── settings.json
```

删除程序不会自动删除待办数据；如需彻底清理，删除上述目录即可。

## 4. 使用方法

1. 启动 `ScheduleReminder.exe`，程序默认选中今天。
2. 在月历中点击今天或未来某一天；左右箭头切换月份；点击“XXXX年XX月”可选择年份和月份。
3. 点击左侧日历右上角的视图切换按钮，在月视图和时间线列表视图之间切换。
4. 在右侧填写：
   - 待办名称；
   - 提醒时间：点击输入框，使用小时/分钟滚动选择器，点击“确定”回填。
5. 点击 **添加待办**。事项会出现在当天列表，并在日历格显示数量标记。
6. 到点后弹出置顶提醒：
   - 点击 **关闭提醒**：关闭弹窗，待办保留为已提醒历史；
   - 输入分钟数并点击 **稍后提醒**：当前弹窗关闭，到新的时间再次提醒。
7. 想删除待办，点击列表右侧的“删除”；已提醒的历史记录同样可以手动删除。
8. 点击窗口右上角关闭按钮时，可选择确认关闭、最小化到系统托盘或取消关闭。

首次启动或版本更新后的第一次启动会显示介绍/更新日志，点击“进入应用”后自动记录当前版本。最小化到系统托盘后程序仍在运行；只有确认关闭或从托盘菜单退出后才会停止提醒。

当前版本不支持：编辑待办、重复提醒、系统级后台通知、开机自启、跨设备同步。

## 5. 开发与打包

### 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖提醒时间解析、稍后提醒、已提醒历史、到期排序、JSON 持久化、损坏数据备份、日期/时间选择面板、视图切换、回到今天按钮、关闭确认、首次启动/更新日志、版本记录和提醒弹窗不自动关闭等行为。

### 安装打包依赖

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### 使用构建脚本（推荐）

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

输出：

```text
dist\ScheduleReminder.exe
```

### 直接使用 PyInstaller 命令

```powershell
.\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --noupx `
  --name ScheduleReminder `
  --icon assets/icon.ico `
  --add-data "assets/icon.ico;assets" `
  --add-data "assets/icon.png;assets" `
  --hidden-import pystray._win32 `
  --version-file version_info.txt `
  main.py
```

## 6. 打包注意事项

- **必须在 Windows x64 上构建**：PyInstaller 不支持从 Linux/macOS 交叉编译 Windows exe。
- **使用 Python 3.12 x64 构建**：需要包含 Tcl/Tk；建议使用 python.org 官方安装包。当前构建使用 Python 3.12.14 + PyInstaller 6.22.3，并包含 pystray 0.19.5 / Pillow 12.3.0。
- `--onefile` 会把 Tcl/Tk 等运行时打进 exe，首次启动需要解压，可能比源码运行慢几秒。
- `--windowed` 不显示控制台；调试时请先用源码运行，或临时改用 `--console` 重新打包。
- `--add-data "assets/icon.ico;assets"` 和 `--add-data "assets/icon.png;assets"` 中的分号是 Windows 路径分隔符；图标用于窗口图标和系统托盘。
- `--hidden-import pystray._win32` 确保 PyInstaller 打包 Windows 托盘后端。
- `--version-file` 写入 `0.3.0` 的 Windows 文件版本信息；发布新版本时同步修改 `version_info.txt` 和 `schedule_reminder/core.py` 中的 `APP_VERSION`。
- 当前 exe **未签名**，SmartScreen 会提示未知发布者。公开分发建议购买并配置 Authenticode 代码签名证书。
- PyInstaller 单文件程序可能被杀毒软件误报；请勿建议用户关闭杀毒软件。可提交样本给安全厂商做误报分析，并保持 `--noupx`。
- 发布前在干净的 Windows 虚拟机中测试：无需 Python，能够启动、创建待办、到点弹窗、稍后提醒和关闭提醒。
- `build/`、`dist/`、`.venv/`、`*.spec` 和 `__pycache__/` 已被 `.gitignore` 忽略；不要把本机虚拟环境提交到仓库。
- 程序数据位于 `%APPDATA%\ScheduleReminder\`，不会写进 exe 所在目录；升级或替换 exe 不影响已有待办。

## 7. 项目结构

```text
.
├── main.py                       # 程序入口
├── schedule_reminder/
│   ├── __init__.py
│   ├── app.py                    # Tkinter 界面、提醒弹窗、托盘和关闭确认
│   ├── core.py                   # 待办模型、时间逻辑、JSON 存储
│   └── version_notes.py          # 应用介绍和版本更新日志
├── tests/
│   ├── test_core.py
│   └── test_ui.py
├── assets/
│   ├── icon.ico                  # exe 和窗口图标
│   └── icon.png                  # README 与系统托盘图标
├── build.ps1                     # PyInstaller 构建脚本
├── requirements.txt              # 运行时依赖：pystray、Pillow
├── requirements-dev.txt          # 运行时依赖 + PyInstaller
├── version_info.txt              # Windows exe 版本信息
├── CHANGELOG.md                  # 版本变更记录
├── .gitignore
├── LICENSE
└── README.md
```

## 8. 版本

- **v0.3.0**：新增关闭确认与系统托盘、并排视图图标、首次启动/版本更新日志和本地版本记录。
- **v0.2.0**：新增年月选择面板、小时/分钟滚动时间选择器、已提醒历史、按选中日期显示“回到今天”，以及月视图/时间线视图切换；优化已提醒条目样式。
- **v0.1.0**：首个 Windows 桌面版本，包含日历、待办、到点提醒、取消、稍后提醒、本地持久化和 PyInstaller 打包。

## License

[MIT](LICENSE)
