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
        self.old_skip_version = os.environ.get("SCHEDULE_REMINDER_SKIP_VERSION_DIALOG")
        os.environ["SCHEDULE_REMINDER_SKIP_VERSION_DIALOG"] = "1"
        self.app = ScheduleReminderApp(self.root)
        self.root.update_idletasks()
        self.root.update()

    def tearDown(self) -> None:
        try:
            if self.app.reminder_dialog is not None:
                self.app.reminder_dialog._close()
            self.app.quit_app()
        finally:
            if self.old_data_dir is None:
                os.environ.pop("SCHEDULE_REMINDER_DATA_DIR", None)
            else:
                os.environ["SCHEDULE_REMINDER_DATA_DIR"] = self.old_data_dir
            if self.old_multi is None:
                os.environ.pop("SCHEDULE_REMINDER_ALLOW_MULTI", None)
            else:
                os.environ["SCHEDULE_REMINDER_ALLOW_MULTI"] = self.old_multi
            if self.old_skip_version is None:
                os.environ.pop("SCHEDULE_REMINDER_SKIP_VERSION_DIALOG", None)
            else:
                os.environ["SCHEDULE_REMINDER_SKIP_VERSION_DIALOG"] = self.old_skip_version
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
        self.assertEqual(len(self.app.todos), 1)
        self.assertIsNotNone(self.app.todos[0].fired_at)

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

    def test_view_toggle_keeps_selected_date_and_restores_calendar(self) -> None:
        selected = self.app.selected_date
        self.assertEqual(len(self.app.view_switch.winfo_children()), 2)
        self.app.toggle_view()
        self.root.update()
        self.assertEqual(self.app.view_mode, "timeline")
        self.assertEqual(self.app.selected_date, selected)
        self.assertGreater(len(self.app.timeline_scroll.inner.winfo_children()), 20)
        self.app.toggle_view()
        self.root.update()
        self.assertEqual(self.app.view_mode, "month")
        self.assertEqual(len(self.app._day_cells), 42)

    def test_close_confirmation_can_be_cancelled(self) -> None:
        self.app._on_close()
        self.root.update()
        self.assertIsNotNone(self.app.close_dialog)
        assert self.app.close_dialog is not None
        self.app.close_dialog._cancel()
        self.root.update()
        self.assertIsNone(self.app.close_dialog)

    def test_version_dialog_saves_current_version(self) -> None:
        os.environ.pop("SCHEDULE_REMINDER_SKIP_VERSION_DIALOG", None)
        self.app._maybe_show_version_dialog()
        self.root.update()
        self.assertIsNotNone(self.app.version_dialog)
        assert self.app.version_dialog is not None
        self.app.version_dialog._finish()
        self.root.update()
        self.assertIsNone(self.app.version_dialog)
        loaded = self.app.settings_store.load()
        self.assertEqual(loaded.last_version, "0.3.0")

    def test_today_button_visibility_follows_selected_date(self) -> None:
        self.assertFalse(self.app._today_button_visible)
        self.app.select_date(date.today() + timedelta(days=1))
        self.root.update()
        self.assertTrue(self.app._today_button_visible)
        self.app.go_today()
        self.root.update()
        self.assertFalse(self.app._today_button_visible)

    def test_time_picker_confirm_and_cancel(self) -> None:
        self.app.time_var.set("09:30")
        self.app.show_time_picker()
        self.root.update()
        self.assertTrue(self.app.time_picker_open)
        self.app._time_hour_list.selection_clear(0, "end")
        self.app._time_hour_list.selection_set(14)
        self.app._time_minute_list.selection_clear(0, "end")
        self.app._time_minute_list.selection_set(45)
        self.app.confirm_time_picker()
        self.assertEqual(self.app.time_var.get(), "14:45")
        self.assertFalse(self.app.time_picker_open)

        self.app.time_var.set("08:15")
        self.app.show_time_picker()
        self.root.update()
        self.app.hide_time_picker()
        self.assertEqual(self.app.time_var.get(), "08:15")

    def test_month_picker_changes_calendar_view(self) -> None:
        self.app.toggle_month_picker()
        self.root.update()
        self.assertTrue(self.app.month_picker_open)
        self.app.choose_month(2)
        self.root.update()
        self.assertFalse(self.app.month_picker_open)
        self.assertEqual(self.app.view_month, 2)


if __name__ == "__main__":
    unittest.main()
