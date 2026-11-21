"""In-app release notes and version comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .core import APP_DISPLAY_NAME, APP_VERSION


@dataclass(frozen=True, slots=True)
class ReleaseNote:
    version: str
    date: str
    title: str
    bullets: tuple[str, ...]


RELEASES: tuple[ReleaseNote, ...] = (
    ReleaseNote(
        version="0.4.0",
        date="2026-11-21",
        title="待办修改、时间选择与今日聚焦",
        bullets=(
            "当天待办新增“修改”按钮，可调整名称和提醒时间；已提醒记录同样可以修改。",
            "新增与修改提醒时间都改用新的滚轮选择器，操作更直接。",
            "月视图中的今天使用与“添加待办”一致的强调色，日期更容易定位。",
            "切换到时间线时自动将今天滚动到视图中间，今天的分组使用加粗边框。",
            "提醒弹窗精简底部说明，并整理列表操作、间距和滚动条样式。",
        ),
    ),
    ReleaseNote(
        version="0.3.0",
        date="2026-11-15",
        title="关闭确认、系统托盘与版本提示",
        bullets=(
            "关闭主窗口时先确认，可选择确认关闭、最小化到系统托盘或取消。",
            "最小化到托盘后程序继续运行，到点仍会弹出提醒；托盘菜单可重新打开或退出。",
            "月视图和时间线视图图标改为并排显示，当前视图高亮。",
            "首次启动显示应用介绍和历史更新日志；版本升级后首次启动显示本次更新内容。",
            "新增上次打开版本记录，点击“进入应用”后自动保存当前版本。",
        ),
    ),
    ReleaseNote(
        version="0.2.0",
        date="2026-11-15",
        title="日期/时间选择与提醒历史",
        bullets=(
            "点击年月标题展开年份和月份选择面板。",
            "提醒时间改为小时/分钟滚动选择器，确定后才回填。",
            "提醒触发后保留为已提醒历史，已提醒条目置灰且可手动删除。",
            "“回到今天”仅在选中日期不是今天时显示。",
            "新增月视图与时间线列表视图切换。",
        ),
    ),
    ReleaseNote(
        version="0.1.0",
        date="2026-11-15",
        title="首个 Windows 桌面版本",
        bullets=(
            "月历创建带名称和提醒时间的待办。",
            "到点置顶提醒，不自动关闭。",
            "支持关闭提醒和稍后提醒。",
            "本地 JSON 持久化与单实例运行。",
        ),
    ),
)

INTRO_PARAGRAPHS: tuple[str, ...] = (
    f"{APP_DISPLAY_NAME}是一款本地 Windows 桌面日历待办与提醒程序。",
    "它不需要账号，也不会上传你的日程；所有待办保存在本机。",
    "到点后提醒窗口会置顶显示，直到你明确选择关闭提醒或稍后提醒。",
    "你可以最小化到系统托盘，让程序继续在后台守候提醒。",
)


def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in value.strip().lstrip("vV").split("."):
        digits = "".join(character for character in part if character.isdigit())
        if digits:
            parts.append(int(digits))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(current: str, previous: str) -> bool:
    if not previous.strip():
        return False
    return version_tuple(current) > version_tuple(previous)


def release_for(version: str) -> ReleaseNote | None:
    for release in RELEASES:
        if release.version == version:
            return release
    return None


def current_release() -> ReleaseNote | None:
    return release_for(APP_VERSION)


def format_release(release: ReleaseNote) -> str:
    lines = [f"v{release.version} · {release.date} · {release.title}"]
    lines.extend(f"• {bullet}" for bullet in release.bullets)
    return "\n".join(lines)


def full_history_text() -> str:
    return "\n\n".join(format_release(release) for release in RELEASES)
