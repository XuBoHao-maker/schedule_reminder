"""Core data model and persistence for Schedule Reminder.

This module deliberately has no Tkinter dependency so that scheduling and
storage behavior can be tested without opening a window.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "Schedule Reminder"
APP_DISPLAY_NAME = "日程提醒"
APP_VERSION = "0.3.0"
APP_DIR_NAME = "ScheduleReminder"

MIN_SNOOZE_MINUTES = 1
MAX_SNOOZE_MINUTES = 1440
MAX_TITLE_LENGTH = 100
STORAGE_VERSION = 1

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{1,2})$")
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


class ValidationError(ValueError):
    """Raised when user input or stored data is invalid."""


class StorageError(RuntimeError):
    """Raised when local data cannot be read or written safely."""


def parse_date_key(value: str) -> date:
    """Parse a strict YYYY-MM-DD date string."""
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValidationError("日期格式应为 YYYY-MM-DD。")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("日期不是有效的日历日期。") from exc


def parse_time_text(value: str) -> time:
    """Parse a user-entered 24-hour time such as 9:05 or 09:05."""
    if not isinstance(value, str):
        raise ValidationError("提醒时间格式应为 HH:MM。")
    text = value.strip().translate(_FULLWIDTH_DIGITS).replace("：", ":")
    match = TIME_RE.fullmatch(text)
    if not match:
        raise ValidationError("提醒时间格式应为 HH:MM，例如 09:30。")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValidationError("提醒时间应在 00:00 到 23:59 之间。")
    return time(hour, minute)


def format_date_key(value: date) -> str:
    return value.isoformat()


def format_time_text(value: time) -> str:
    return value.strftime("%H:%M")


def format_date_cn(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日 {WEEKDAYS_CN[value.weekday()]}"


def format_datetime_cn(value: datetime) -> str:
    return f"{format_date_cn(value.date())} {value.strftime('%H:%M')}"


def combine_local(due_date: date, remind_time: time) -> datetime:
    return datetime.combine(due_date, remind_time)


def parse_snooze_minutes(value: str | int) -> int:
    """Validate a snooze duration and return it as an integer."""
    if isinstance(value, bool):
        raise ValidationError("稍后提醒分钟数必须是整数。")
    if isinstance(value, int):
        minutes = value
    else:
        text = str(value).strip().translate(_FULLWIDTH_DIGITS)
        if not re.fullmatch(r"\d+", text):
            raise ValidationError(
                f"稍后提醒分钟数应为 {MIN_SNOOZE_MINUTES}–{MAX_SNOOZE_MINUTES} 的整数。"
            )
        minutes = int(text)
    if not MIN_SNOOZE_MINUTES <= minutes <= MAX_SNOOZE_MINUTES:
        raise ValidationError(
            f"稍后提醒分钟数应为 {MIN_SNOOZE_MINUTES}–{MAX_SNOOZE_MINUTES} 的整数。"
        )
    return minutes


def normalize_title(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("请填写待办名称。")
    title = " ".join(value.split())
    if not title:
        raise ValidationError("请填写待办名称。")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"待办名称不能超过 {MAX_TITLE_LENGTH} 个字符。")
    return title


@dataclass(slots=True)
class Todo:
    id: str
    title: str
    due_date: date
    remind_time: time
    created_at: datetime
    snoozed_until: datetime | None = None
    fired_at: datetime | None = None
    snooze_count: int = 0

    @classmethod
    def create(
        cls,
        title: str,
        due_date: date,
        remind_time: time,
        *,
        created_at: datetime | None = None,
    ) -> "Todo":
        return cls(
            id=uuid.uuid4().hex,
            title=normalize_title(title),
            due_date=due_date,
            remind_time=remind_time,
            created_at=(created_at or datetime.now()).replace(microsecond=0),
        )

    @property
    def scheduled_at(self) -> datetime:
        return combine_local(self.due_date, self.remind_time)

    @property
    def effective_due(self) -> datetime:
        return self.snoozed_until or self.scheduled_at

    def is_due(self, at: datetime) -> bool:
        return self.effective_due <= at

    def snooze(self, minutes: int, *, at: datetime | None = None) -> None:
        minutes = parse_snooze_minutes(minutes)
        base = (at or datetime.now()).replace(microsecond=0)
        self.snoozed_until = base + timedelta(minutes=minutes)
        self.fired_at = None
        self.snooze_count += 1

    def mark_fired(self, *, at: datetime | None = None) -> None:
        self.fired_at = (at or datetime.now()).replace(microsecond=0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "date": format_date_key(self.due_date),
            "time": format_time_text(self.remind_time),
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "snoozed_until": (
                self.snoozed_until.isoformat(timespec="seconds")
                if self.snoozed_until
                else None
            ),
            "fired_at": (
                self.fired_at.isoformat(timespec="seconds")
                if self.fired_at
                else None
            ),
            "snooze_count": self.snooze_count,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Todo | None":
        if not isinstance(data, dict):
            return None
        try:
            todo_id = data.get("id")
            title = normalize_title(data.get("title", ""))
            due_date = parse_date_key(data.get("date") or data.get("due_date"))
            remind_time = parse_time_text(data.get("time") or data.get("remind_time"))
            created_at = datetime.fromisoformat(str(data.get("created_at", "")))
            if created_at.tzinfo is not None:
                created_at = created_at.replace(tzinfo=None)
            snoozed_raw = data.get("snoozed_until")
            snoozed_until = (
                datetime.fromisoformat(str(snoozed_raw)) if snoozed_raw else None
            )
            if snoozed_until and snoozed_until.tzinfo is not None:
                snoozed_until = snoozed_until.replace(tzinfo=None)
            fired_raw = data.get("fired_at")
            fired_at = datetime.fromisoformat(str(fired_raw)) if fired_raw else None
            if fired_at and fired_at.tzinfo is not None:
                fired_at = fired_at.replace(tzinfo=None)
            snooze_count = int(data.get("snooze_count", 0))
            if not isinstance(todo_id, str) or not todo_id:
                return None
            if snooze_count < 0:
                snooze_count = 0
        except (TypeError, ValueError, ValidationError):
            return None
        return cls(
            id=todo_id,
            title=title,
            due_date=due_date,
            remind_time=remind_time,
            created_at=created_at,
            snoozed_until=snoozed_until,
            fired_at=fired_at,
            snooze_count=snooze_count,
        )


def due_todos(todos: Iterable[Todo], at: datetime) -> list[Todo]:
    """Return due, still-pending todos, oldest effective due time first."""
    return sorted(
        (
            todo
            for todo in todos
            if todo.fired_at is None and todo.is_due(at)
        ),
        key=lambda todo: (todo.effective_due, todo.created_at, todo.title.casefold()),
    )


def todos_for_date(todos: Iterable[Todo], due_date: date) -> list[Todo]:
    return sorted(
        (todo for todo in todos if todo.due_date == due_date),
        key=lambda todo: (todo.remind_time, todo.created_at, todo.title.casefold()),
    )


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".schedule-reminder-", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise StorageError(f"无法写入本地数据：{exc}") from exc


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path

    @classmethod
    def for_current_user(cls) -> "AppPaths":
        override = os.environ.get("SCHEDULE_REMINDER_DATA_DIR")
        if override:
            return cls(Path(override).expanduser())
        appdata = os.environ.get("APPDATA")
        if appdata:
            return cls(Path(appdata) / APP_DIR_NAME)
        return cls(Path.home() / ".schedule_reminder")

    @property
    def todos_file(self) -> Path:
        return self.data_dir / "todos.json"

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"


class TodoStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[Todo]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                items = raw.get("todos", [])
            elif isinstance(raw, list):
                items = raw
            else:
                raise ValueError("unsupported root value")
            if not isinstance(items, list):
                raise ValueError("todos is not a list")
            loaded: list[Todo] = []
            for item in items:
                todo = Todo.from_dict(item)
                if todo is not None:
                    loaded.append(todo)
            return loaded
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            backup = self._backup_corrupt_file()
            detail = f"无法读取待办数据：{exc}"
            if backup is not None:
                detail += f"\n原文件已备份到：{backup}"
            raise StorageError(detail) from exc

    def save(self, todos: Iterable[Todo]) -> None:
        payload = {
            "version": STORAGE_VERSION,
            "todos": [todo.to_dict() for todo in todos],
        }
        _atomic_write_json(self.path, payload)

    def _backup_corrupt_file(self) -> Path | None:
        if not self.path.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(
            f"{self.path.stem}.corrupt-{stamp}{self.path.suffix}"
        )
        try:
            shutil.copy2(self.path, backup)
        except OSError:
            return None
        return backup


@dataclass(slots=True)
class Settings:
    snooze_minutes: int = 5
    last_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snooze_minutes": self.snooze_minutes,
            "last_version": self.last_version,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Settings":
        if isinstance(data, dict):
            try:
                snooze_minutes = parse_snooze_minutes(data.get("snooze_minutes", 5))
            except (TypeError, ValueError, ValidationError):
                snooze_minutes = 5
            last_version = data.get("last_version", "")
            if not isinstance(last_version, str):
                last_version = ""
            return cls(
                snooze_minutes=snooze_minutes,
                last_version=last_version.strip(),
            )
        return cls()


class SettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            return Settings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, json.JSONDecodeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        _atomic_write_json(self.path, settings.to_dict())
