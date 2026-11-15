from __future__ import annotations

import os
import tempfile
import time
import tkinter as tk
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from schedule_reminder.app import ScheduleReminderApp
from schedule_reminder.core import Todo, TodoStore


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("SCHEDULE_REMINDER_DATA_DIR")
        os.environ["SCHEDULE_REMINDER_DATA_DIR"] = self.temp_dir.name
        self.old_multi = os.environ.get("SCHEDULE_REMINDER_ALLOW_MULTI")
        os.environ["SCHEDULE_REMINDER_ALLOW_MULTI"] = "1"
        self.app = ScheduleReminderApp(self.root)
        self.root.update_idletasks()
        self.root.update()

    def tearDown(self) -> None:
        try:
            if self.app.reminder_dialog is not None:
                self.app.reminder_dialog._close()
            self.app._on_close()
        finally:
            if self.old_data_dir is None:
                os.environ.pop("SCHEDULE_REMINDER_DATA_DIR", None)
            else:
                os.environ["SCHEDULE_REMINDER_DATA_DIR"] = self.old_data_dir
            if self.old_multi is None:
                os.environ.pop("SCHEDULE_REMINDER_ALLOW_MULTI", None)
            else:
                os.environ["SCHEDULE_REMINDER_ALLOW_MULTI"] = self.old_multi
            self.temp_dir.cleanup()

    def _add_due_todo(self, title: str = "测试提醒") -> Todo:
        now = datetime.now().replace(microsecond=0) - timedelta(minutes=1)
        todo = Todo.create(
            title,
            now.date(),
            now.time(),
            created_at=now - timedelta(minutes=5),
        )
        self.app.todos.append(todo)
        self.app.check_for_due()
        self.root.update_idletasks()
        self.root.update()
        return todo

    def test_calendar_builds_42_day_cells(self) -> None:
        self.assertEqual(len(self.app._day_cells), 42)
        self.assertTrue(self.app.month_label.cget("text").endswith("月"))

    def test_add_todo_persists_to_json(self) -> None:
        self.app.selected_date = date.today() + timedelta(days=1)
        self.app.view_year = self.app.selected_date.year
        self.app.view_month = self.app.selected_date.month
        self.app.title_var.set("新的待办")
        self.app.time_var.set("09:30")
        self.app.add_todo()
        self.root.update()
        self.assertEqual(len(self.app.todos), 1)
        loaded = TodoStore(Path(self.temp_dir.name) / "todos.json").load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "新的待办")

    def test_due_todo_opens_reminder_and_escape_does_not_close(self) -> None:
        self._add_due_todo()
        dialog = self.app.reminder_dialog
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertTrue(dialog.window.overrideredirect())
        dialog.window.event_generate("<Escape>")
        self.root.update()
        time.sleep(0.15)
        self.root.update()
        self.assertFalse(dialog.closed)
        dialog._cancel()
        self.root.update()
        self.assertIsNone(self.app.reminder_dialog)
        self.assertEqual(self.app.todos, [])

    def test_snooze_persists_and_closes_dialog(self) -> None:
        self._add_due_todo("稍后测试")
        dialog = self.app.reminder_dialog
        self.assertIsNotNone(dialog)
        assert dialog is not None
        dialog.snooze_var.set("7")
        dialog._snooze()
        self.root.update()
        self.assertIsNone(self.app.reminder_dialog)
        self.assertEqual(len(self.app.todos), 1)
        self.assertIsNotNone(self.app.todos[0].snoozed_until)
        assert self.app.todos[0].snoozed_until is not None
        self.assertGreater(
            self.app.todos[0].snoozed_until,
            datetime.now() + timedelta(minutes=6),
        )
        self.assertEqual(self.app.settings.snooze_minutes, 7)

    def test_reminder_stays_open_when_no_action(self) -> None:
        self._add_due_todo("不自动关闭")
        dialog = self.app.reminder_dialog
        assert dialog is not None
        time.sleep(1.15)
        self.root.update()
        self.assertIsNotNone(self.app.reminder_dialog)
        self.assertFalse(dialog.closed)
        dialog._cancel()
        self.root.update()


if __name__ == "__main__":
    unittest.main()
