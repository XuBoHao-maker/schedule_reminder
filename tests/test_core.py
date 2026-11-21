from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from schedule_reminder.core import (
    AppPaths,
    Settings,
    SettingsStore,
    StorageError,
    Todo,
    TodoStore,
    ValidationError,
    due_todos,
    format_date_cn,
    format_datetime_cn,
    parse_snooze_minutes,
    parse_time_text,
    todos_for_date,
)
from schedule_reminder.version_notes import is_newer_version, version_tuple


class VersionTests(unittest.TestCase):
    def test_version_comparison(self) -> None:
        self.assertEqual(version_tuple("v0.4.0"), (0, 4, 0))
        self.assertTrue(is_newer_version("0.4.0", "0.3.0"))
        self.assertFalse(is_newer_version("0.4.0", "0.4.0"))
        self.assertFalse(is_newer_version("0.4.0", ""))


class TimeParsingTests(unittest.TestCase):
    def test_accepts_common_time_formats(self) -> None:
        self.assertEqual(parse_time_text("09:30"), time(9, 30))
        self.assertEqual(parse_time_text("9:05"), time(9, 5))
        self.assertEqual(parse_time_text(" 23：59 "), time(23, 59))

    def test_rejects_invalid_time(self) -> None:
        for value in ("", "24:00", "12:60", "1230", "12", "12:3:4"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_time_text(value)

    def test_snooze_boundaries(self) -> None:
        self.assertEqual(parse_snooze_minutes(1), 1)
        self.assertEqual(parse_snooze_minutes("1440"), 1440)
        for value in (0, 1441, -1, "1.5", "", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_snooze_minutes(value)


class TodoTests(unittest.TestCase):
    def test_create_normalizes_title_and_schedules(self) -> None:
        created = datetime(2026, 11, 15, 9, 0, 0)
        todo = Todo.create(
            "  提交   周报  ",
            date(2026, 11, 20),
            time(15, 0),
            created_at=created,
        )
        self.assertEqual(todo.title, "提交 周报")
        self.assertEqual(todo.scheduled_at, datetime(2026, 11, 20, 15, 0))
        self.assertFalse(todo.is_due(datetime(2026, 11, 20, 14, 59)))
        self.assertTrue(todo.is_due(datetime(2026, 11, 20, 15, 0)))

    def test_snooze_moves_effective_due_and_increments_count(self) -> None:
        todo = Todo.create(
            "复盘",
            date(2026, 11, 20),
            time(15, 0),
            created_at=datetime(2026, 11, 15, 9, 0),
        )
        now = datetime(2026, 11, 20, 15, 0, 30)
        todo.snooze(10, at=now)
        self.assertEqual(todo.snoozed_until, datetime(2026, 11, 20, 15, 10, 30))
        self.assertEqual(todo.snooze_count, 1)
        self.assertFalse(todo.is_due(datetime(2026, 11, 20, 15, 10)))
        self.assertTrue(todo.is_due(datetime(2026, 11, 20, 15, 10, 30)))

    def test_due_todos_are_sorted_and_future_is_excluded(self) -> None:
        base = datetime(2026, 11, 20, 9, 0)
        later = Todo.create(
            "later", date(2026, 11, 20), time(10, 0), created_at=base
        )
        earlier = Todo.create(
            "earlier", date(2026, 11, 20), time(9, 30), created_at=base
        )
        future = Todo.create(
            "future", date(2026, 11, 21), time(9, 0), created_at=base
        )
        result = due_todos([later, future, earlier], datetime(2026, 11, 20, 10, 0))
        self.assertEqual([todo.title for todo in result], ["earlier", "later"])

    def test_fired_todo_is_retained_but_no_longer_due(self) -> None:
        todo = Todo.create(
            "已提醒",
            date(2026, 11, 20),
            time(9, 0),
            created_at=datetime(2026, 11, 15, 9, 0),
        )
        todo.mark_fired(at=datetime(2026, 11, 20, 9, 0, 5))
        self.assertIsNotNone(todo.fired_at)
        self.assertEqual(todo.fired_at, datetime(2026, 11, 20, 9, 0, 5))
        self.assertEqual(due_todos([todo], datetime(2026, 11, 20, 10, 0)), [])

    def test_todos_for_date(self) -> None:
        base = datetime(2026, 11, 20, 9, 0)
        morning = Todo.create(
            "morning", date(2026, 11, 20), time(9, 0), created_at=base
        )
        evening = Todo.create(
            "evening", date(2026, 11, 20), time(18, 0), created_at=base
        )
        other = Todo.create("other", date(2026, 11, 21), time(9, 0), created_at=base)
        result = todos_for_date([evening, other, morning], date(2026, 11, 20))
        self.assertEqual([todo.title for todo in result], ["morning", "evening"])

    def test_round_trip_dict(self) -> None:
        todo = Todo.create(
            "带中文的待办",
            date(2026, 11, 20),
            time(9, 30),
            created_at=datetime(2026, 11, 15, 12, 0),
        )
        todo.snooze(5, at=datetime(2026, 11, 20, 9, 30))
        todo.mark_fired(at=datetime(2026, 11, 20, 9, 35))
        restored = Todo.from_dict(todo.to_dict())
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.title, todo.title)
        self.assertEqual(restored.due_date, todo.due_date)
        self.assertEqual(restored.remind_time, todo.remind_time)
        self.assertEqual(restored.snoozed_until, todo.snoozed_until)
        self.assertEqual(restored.fired_at, todo.fired_at)
        self.assertEqual(restored.snooze_count, 1)

    def test_invalid_dict_is_rejected(self) -> None:
        self.assertIsNone(Todo.from_dict({}))
        self.assertIsNone(Todo.from_dict({"title": "", "date": "x", "time": "09:00"}))

    def test_chinese_format_helpers(self) -> None:
        self.assertEqual(
            format_date_cn(date(2026, 11, 15)),
            "2026年11月15日 周日",
        )
        self.assertEqual(
            format_datetime_cn(datetime(2026, 11, 15, 9, 5)),
            "2026年11月15日 周日 09:05",
        )


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_todo_store_round_trip(self) -> None:
        store = TodoStore(self.root / "todos.json")
        todo = Todo.create(
            "测试",
            date(2026, 11, 20),
            time(9, 30),
            created_at=datetime(2026, 11, 15, 12, 0),
        )
        store.save([todo])
        loaded = store.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "测试")
        payload = json.loads((self.root / "todos.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)

    def test_empty_store_returns_empty(self) -> None:
        store = TodoStore(self.root / "missing.json")
        self.assertEqual(store.load(), [])

    def test_corrupt_store_is_backed_up(self) -> None:
        path = self.root / "todos.json"
        path.write_text("{not valid json", encoding="utf-8")
        store = TodoStore(path)
        with self.assertRaises(StorageError) as context:
            store.load()
        self.assertIn("备份", str(context.exception))
        backups = list(self.root.glob("todos.corrupt-*.json"))
        self.assertEqual(len(backups), 1)

    def test_settings_round_trip_and_corrupt_default(self) -> None:
        path = self.root / "settings.json"
        store = SettingsStore(path)
        self.assertEqual(store.load().snooze_minutes, 5)
        self.assertEqual(store.load().last_version, "")
        store.save(Settings(snooze_minutes=17, last_version="0.2.0"))
        loaded = store.load()
        self.assertEqual(loaded.snooze_minutes, 17)
        self.assertEqual(loaded.last_version, "0.2.0")
        path.write_text("broken", encoding="utf-8")
        self.assertEqual(store.load().snooze_minutes, 5)
        self.assertEqual(store.load().last_version, "")

    def test_app_paths_env_override(self) -> None:
        old = os.environ.get("SCHEDULE_REMINDER_DATA_DIR")
        try:
            os.environ["SCHEDULE_REMINDER_DATA_DIR"] = str(self.root / "custom")
            paths = AppPaths.for_current_user()
            self.assertEqual(paths.data_dir, self.root / "custom")
            self.assertEqual(paths.todos_file.name, "todos.json")
        finally:
            if old is None:
                os.environ.pop("SCHEDULE_REMINDER_DATA_DIR", None)
            else:
                os.environ["SCHEDULE_REMINDER_DATA_DIR"] = old


if __name__ == "__main__":
    unittest.main()
