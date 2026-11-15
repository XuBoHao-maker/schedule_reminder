"""Tkinter desktop UI for Schedule Reminder."""

from __future__ import annotations

import calendar
import ctypes
import os
import sys
import traceback
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from .core import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION,
    AppPaths,
    Settings,
    SettingsStore,
    StorageError,
    Todo,
    TodoStore,
    ValidationError,
    combine_local,
    due_todos,
    format_date_cn,
    format_datetime_cn,
    format_time_text,
    parse_snooze_minutes,
    parse_time_text,
    todos_for_date,
)

COLORS = {
    "paper": "#f6f0e4",
    "card": "#fffdf8",
    "warm": "#fffaf0",
    "ink": "#26221c",
    "ink_soft": "#4c463d",
    "muted": "#746b5e",
    "line": "#e7ddcb",
    "line_strong": "#d8cab2",
    "accent": "#c44620",
    "accent_deep": "#a83818",
    "accent_soft": "#fbe3d7",
    "gold": "#d9a53a",
    "green": "#2e7259",
    "red": "#b43a2f",
    "white": "#fff9ee",
    "outside": "#b9ad9c",
    "past": "#a79d8f",
}

_MUTEX_HANDLE = None


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def choose_font(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"):
        if candidate in available:
            return candidate
    return "TkDefaultFont"


def _draw_calendar_logo(canvas: tk.Canvas, size: int = 52) -> None:
    canvas.create_oval(1, 1, size - 1, size - 1, fill=COLORS["accent"], outline="")
    left, top, right, bottom = 14, 15, size - 14, size - 13
    canvas.create_rectangle(
        left, top, right, bottom, outline=COLORS["white"], width=2
    )
    canvas.create_line(left, top + 7, right, top + 7, fill=COLORS["white"], width=2)
    canvas.create_line(left + 6, 10, left + 6, top + 3, fill=COLORS["white"], width=2)
    canvas.create_line(
        right - 6, 10, right - 6, top + 3, fill=COLORS["white"], width=2
    )
    canvas.create_line(
        left + 6, top + 15, left + 11, top + 15, fill=COLORS["white"], width=2
    )
    canvas.create_line(
        right - 11, top + 15, right - 6, top + 15, fill=COLORS["white"], width=2
    )


def _draw_alarm_logo(canvas: tk.Canvas, size: int = 56) -> None:
    canvas.create_oval(3, 3, size - 3, size - 3, fill=COLORS["accent"], outline="")
    center = size / 2
    canvas.create_oval(
        center - 13,
        center - 13,
        center + 13,
        center + 13,
        outline=COLORS["white"],
        width=2,
    )
    canvas.create_line(
        center,
        center - 8,
        center,
        center,
        fill=COLORS["white"],
        width=2,
    )
    canvas.create_line(
        center,
        center,
        center + 6,
        center + 4,
        fill=COLORS["white"],
        width=2,
    )
    canvas.create_line(11, 10, 17, 6, fill=COLORS["white"], width=2)
    canvas.create_line(size - 11, 10, size - 17, 6, fill=COLORS["white"], width=2)


class ScrollableFrame(tk.Frame):
    """A vertically scrollable frame that keeps the scrollbar out of the way."""

    def __init__(self, master: tk.Misc, bg: str):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event: tk.Event) -> None:
        if not self.canvas.winfo_exists():
            return
        x, y = self.winfo_pointerxy()
        left = self.canvas.winfo_rootx()
        top = self.canvas.winfo_rooty()
        if (
            left <= x < left + self.canvas.winfo_width()
            and top <= y < top + self.canvas.winfo_height()
        ):
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


class DayCell(tk.Frame):
    """One clickable day in the calendar grid."""

    def __init__(self, master: tk.Misc, app: "ScheduleReminderApp", day: date, count: int):
        super().__init__(
            master,
            bg=COLORS["card"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            bd=0,
            cursor="hand2",
        )
        self.app = app
        self.day = day
        self.count = count
        self.selected = False
        self.today = False
        self.hover = False
        self.day_label = tk.Label(
            self,
            text=str(day.day),
            bg=COLORS["card"],
            fg=COLORS["ink"],
            font=(app.font_family, 12, "bold"),
            cursor="hand2",
        )
        self.count_label = tk.Label(
            self,
            text=f"{count} 项" if count else " ",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(app.font_family, 8),
            cursor="hand2",
        )
        self.day_label.pack(pady=(9, 0))
        self.count_label.pack(pady=(1, 5))
        for widget in (self, self.day_label, self.count_label):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, _event: tk.Event) -> None:
        self.app.select_date(self.day)

    def _on_enter(self, _event: tk.Event) -> None:
        self.hover = True
        self._apply_colors()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hover = False
        self._apply_colors()

    def set_state(self, *, selected: bool, today: bool) -> None:
        self.selected = selected
        self.today = today
        self._apply_colors()

    def _apply_colors(self) -> None:
        in_month = (
            self.day.year == self.app.view_year
            and self.day.month == self.app.view_month
        )
        is_past = self.day < date.today()
        background = COLORS["card"]
        foreground = COLORS["ink"] if in_month else COLORS["outside"]
        border = COLORS["line"]
        count_fg = COLORS["muted"]
        if self.selected:
            background = COLORS["ink"]
            foreground = COLORS["white"]
            border = COLORS["ink"]
            count_fg = COLORS["gold"]
        elif self.today:
            background = "#fff3ea"
            foreground = COLORS["accent_deep"]
            border = "#eac3b3"
            count_fg = COLORS["accent_deep"]
        elif self.hover:
            background = "#f8f0e1"
            border = COLORS["line_strong"]
        elif is_past:
            foreground = COLORS["past"]
        self.configure(bg=background, highlightbackground=border)
        self.day_label.configure(bg=background, fg=foreground)
        self.count_label.configure(
            bg=background,
            fg=count_fg,
            text=f"{self.count} 项" if self.count else " ",
        )


class ReminderDialog:
    """A deliberately non-dismissible reminder window."""

    WIDTH = 500

    def __init__(self, app: "ScheduleReminderApp", todo: Todo):
        self.app = app
        self.todo = todo
        self.closed = False
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title(f"待办提醒 - {APP_NAME}")
        self.window.configure(bg=COLORS["accent_deep"])
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        self.window.bind("<Escape>", lambda _event: "break")
        self.window.bind("<Alt-F4>", lambda _event: "break")
        self.window.bind("<Return>", lambda _event: self._snooze())

        self.outer = tk.Frame(self.window, bg=COLORS["accent_deep"])
        self.outer.pack(fill="both", expand=True, padx=1, pady=1)
        self.card = tk.Frame(self.outer, bg=COLORS["card"])
        self.card.pack(fill="both", expand=True, padx=1, pady=1)

        top = tk.Frame(self.card, bg=COLORS["card"])
        top.pack(fill="x", padx=28, pady=(26, 0))
        logo = tk.Canvas(
            top, width=56, height=56, bg=COLORS["card"], highlightthickness=0
        )
        _draw_alarm_logo(logo)
        logo.pack(side="left", anchor="n")
        heading = tk.Frame(top, bg=COLORS["card"])
        heading.pack(side="left", padx=(14, 0), anchor="n")
        tk.Label(
            heading,
            text="待办提醒",
            bg=COLORS["card"],
            fg=COLORS["accent_deep"],
            font=(app.font_family, 9, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            heading,
            text="现在该处理这件事了",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(app.font_family, 9),
        ).pack(anchor="w")

        tk.Label(
            self.card,
            text=todo.title,
            bg=COLORS["card"],
            fg=COLORS["ink"],
            font=(app.font_family, 20, "bold"),
            justify="left",
            anchor="w",
            wraplength=440,
        ).pack(fill="x", padx=28, pady=(20, 0))

        details = f"原定 {format_datetime_cn(todo.scheduled_at)}"
        if todo.snooze_count:
            details += f" · 已稍后 {todo.snooze_count} 次"
        tk.Label(
            self.card,
            text=details,
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(app.font_family, 9),
            anchor="w",
            justify="left",
            wraplength=440,
        ).pack(fill="x", padx=28, pady=(7, 0))

        snooze_box = tk.Frame(
            self.card,
            bg=COLORS["warm"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        snooze_box.pack(fill="x", padx=28, pady=(20, 0))
        row = tk.Frame(snooze_box, bg=COLORS["warm"])
        row.pack(fill="x", padx=14, pady=(12, 5))
        tk.Label(
            row,
            text="稍后提醒",
            bg=COLORS["warm"],
            fg=COLORS["ink_soft"],
            font=(app.font_family, 10, "bold"),
        ).pack(side="left")
        self.snooze_var = tk.StringVar(value=str(app.settings.snooze_minutes))
        self.snooze_entry = tk.Spinbox(
            row,
            from_=1,
            to=1440,
            width=6,
            textvariable=self.snooze_var,
            font=(app.font_family, 11),
            bg=COLORS["white"],
            fg=COLORS["ink"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line_strong"],
            highlightcolor=COLORS["accent"],
            justify="center",
        )
        self.snooze_entry.pack(side="left", padx=(10, 7), ipady=4)
        tk.Label(
            row,
            text="分钟后",
            bg=COLORS["warm"],
            fg=COLORS["ink_soft"],
            font=(app.font_family, 9),
        ).pack(side="left")
        tk.Label(
            snooze_box,
            text="输入 1–1440 之间的整数分钟，到点后会再次提醒。",
            bg=COLORS["warm"],
            fg=COLORS["muted"],
            font=(app.font_family, 8),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        buttons = tk.Frame(self.card, bg=COLORS["card"])
        buttons.pack(fill="x", padx=28, pady=(16, 0))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        self.cancel_button = app.make_button(
            buttons,
            "取消待办",
            self._cancel,
            kind="ghost",
        )
        self.cancel_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.snooze_button = app.make_button(
            buttons,
            "稍后提醒",
            self._snooze,
            kind="primary",
        )
        self.snooze_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.error_label = tk.Label(
            self.card,
            text="",
            bg=COLORS["card"],
            fg=COLORS["red"],
            font=(app.font_family, 8),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        self.error_label.pack(fill="x", padx=28, pady=(8, 0))
        tk.Label(
            self.card,
            text="此弹窗不会自动关闭，请选择“取消待办”或“稍后提醒”。",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(app.font_family, 8),
            anchor="center",
        ).pack(fill="x", padx=28, pady=(3, 22))

        self.window.update_idletasks()
        height = max(420, self.window.winfo_reqheight())
        x = (self.window.winfo_screenwidth() - self.WIDTH) // 2
        y = max(20, (self.window.winfo_screenheight() - height) // 2)
        self.window.geometry(f"{self.WIDTH}x{height}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        self.window.grab_set()
        self.window.after(80, self._focus)

    def _focus(self) -> None:
        if self.closed:
            return
        try:
            self.window.focus_force()
            self.snooze_entry.focus_set()
            self.snooze_entry.selection_range(0, "end")
        except tk.TclError:
            pass

    def bring_to_front(self) -> None:
        if self.closed:
            return
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        self.window.focus_force()

    def _cancel(self) -> None:
        if self.closed:
            return
        if not self.app.cancel_todo(self.todo.id):
            return
        self._close()

    def _snooze(self) -> None:
        if self.closed:
            return
        try:
            minutes = parse_snooze_minutes(self.snooze_var.get())
        except ValidationError as exc:
            self.error_label.configure(text=str(exc))
            self.snooze_entry.focus_set()
            self.snooze_entry.selection_range(0, "end")
            return
        if not self.app.snooze_todo(self.todo.id, minutes):
            return
        self._close()

    def _close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        if self.app.reminder_dialog is self:
            self.app.reminder_dialog = None
        self.app.root.after(30, self.app.check_for_due)


class ScheduleReminderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.paths = AppPaths.for_current_user()
        self.todo_store = TodoStore(self.paths.todos_file)
        self.settings_store = SettingsStore(self.paths.settings_file)
        self.settings = self.settings_store.load()
        self.load_error: str | None = None
        try:
            self.todos = self.todo_store.load()
        except StorageError as exc:
            self.todos = []
            self.load_error = str(exc)

        self.font_family = choose_font(root)
        self.selected_date = date.today()
        self.view_year = self.selected_date.year
        self.view_month = self.selected_date.month
        self.reminder_dialog: ReminderDialog | None = None
        self._closing = False
        self._day_cells: list[DayCell] = []
        self._calendar_initialized = False

        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.configure(bg=COLORS["paper"])
        self.root.minsize(980, 640)
        self._set_window_geometry()
        self._set_icon()
        self._build_ui()
        self._set_default_time()
        self._refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.report_callback_exception = self._report_callback_exception
        if self.load_error:
            self.root.after(
                150,
                lambda: messagebox.showwarning(
                    "读取待办失败",
                    self.load_error,
                    parent=self.root,
                ),
            )
        self.root.after(300, self.check_for_due)
        self.root.after(1000, self._tick)
        self.root.after(120, self.title_entry.focus_set)

    def _set_window_geometry(self) -> None:
        width, height = 1120, 720
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(width, max(980, screen_w - 80))
        height = min(height, max(640, screen_h - 100))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _set_icon(self) -> None:
        icon = resource_path("assets/icon.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        family = self.font_family
        outer = tk.Frame(self.root, bg=COLORS["paper"])
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        header = tk.Frame(outer, bg=COLORS["paper"])
        header.pack(fill="x")
        brand = tk.Frame(header, bg=COLORS["paper"])
        brand.pack(side="left")
        logo = tk.Canvas(
            brand, width=52, height=52, bg=COLORS["paper"], highlightthickness=0
        )
        _draw_calendar_logo(logo)
        logo.pack(side="left")
        title_block = tk.Frame(brand, bg=COLORS["paper"])
        title_block.pack(side="left", padx=(14, 0))
        tk.Label(
            title_block,
            text=APP_DISPLAY_NAME,
            bg=COLORS["paper"],
            fg=COLORS["ink"],
            font=(family, 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="把重要的事，留在日历上。",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=(family, 9),
        ).pack(anchor="w", pady=(2, 0))
        self.today_button = self.make_button(
            header, "回到今天", self.go_today, kind="ghost"
        )
        self.today_button.pack(side="right", pady=(5, 0))

        main = tk.Frame(outer, bg=COLORS["paper"])
        main.pack(fill="both", expand=True, pady=(22, 0))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=3, minsize=560)
        main.grid_columnconfigure(1, weight=2, minsize=360)

        calendar_card = tk.Frame(
            main,
            bg=COLORS["card"],
            highlightbackground=COLORS["line_strong"],
            highlightthickness=1,
        )
        calendar_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel_card = tk.Frame(
            main,
            bg=COLORS["card"],
            highlightbackground=COLORS["line_strong"],
            highlightthickness=1,
        )
        panel_card.grid(row=0, column=1, sticky="nsew")

        self._build_calendar(calendar_card)
        self._build_panel(panel_card)

    def _build_calendar(self, parent: tk.Frame) -> None:
        family = self.font_family
        inner = tk.Frame(parent, bg=COLORS["card"])
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        month_bar = tk.Frame(inner, bg=COLORS["card"])
        month_bar.pack(fill="x", pady=(0, 12))
        self.prev_button = self.make_button(
            month_bar, "‹", self.previous_month, kind="circle"
        )
        self.prev_button.pack(side="left")
        self.month_label = tk.Label(
            month_bar,
            text="",
            bg=COLORS["card"],
            fg=COLORS["ink"],
            font=(family, 17, "bold"),
        )
        self.month_label.pack(side="left", expand=True)
        self.next_button = self.make_button(
            month_bar, "›", self.next_month, kind="circle"
        )
        self.next_button.pack(side="right")

        weekdays = tk.Frame(inner, bg=COLORS["card"])
        weekdays.pack(fill="x", pady=(0, 5))
        for column, name in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            weekdays.grid_columnconfigure(column, weight=1)
            tk.Label(
                weekdays,
                text=name,
                bg=COLORS["card"],
                fg=COLORS["accent_deep"] if column >= 5 else COLORS["muted"],
                font=(family, 8, "bold"),
            ).grid(row=0, column=column, sticky="ew")

        self.calendar_grid = tk.Frame(inner, bg=COLORS["card"])
        self.calendar_grid.pack(fill="both", expand=True)
        for column in range(7):
            self.calendar_grid.grid_columnconfigure(column, weight=1, uniform="day")
        for row in range(6):
            self.calendar_grid.grid_rowconfigure(row, weight=1, uniform="day")

    def _build_panel(self, parent: tk.Frame) -> None:
        family = self.font_family
        inner = tk.Frame(parent, bg=COLORS["card"])
        inner.pack(fill="both", expand=True, padx=22, pady=19)

        head = tk.Frame(inner, bg=COLORS["card"])
        head.pack(fill="x")
        head_left = tk.Frame(head, bg=COLORS["card"])
        head_left.pack(side="left", anchor="n")
        tk.Label(
            head_left,
            text="选中日期",
            bg=COLORS["card"],
            fg=COLORS["accent_deep"],
            font=(family, 8, "bold"),
        ).pack(anchor="w")
        self.selected_label = tk.Label(
            head_left,
            text="",
            bg=COLORS["card"],
            fg=COLORS["ink"],
            font=(family, 15, "bold"),
        )
        self.selected_label.pack(anchor="w", pady=(2, 0))
        self.count_label = tk.Label(
            head,
            text="0 项",
            bg="#f4ecdd",
            fg=COLORS["ink_soft"],
            font=(family, 8, "bold"),
            padx=9,
            pady=5,
        )
        self.count_label.pack(side="right", anchor="n")

        self.form_frame = tk.Frame(inner, bg=COLORS["card"])
        self.form_frame.pack(fill="x", pady=(18, 0))
        self.title_var = tk.StringVar()
        self.time_var = tk.StringVar()
        tk.Label(
            self.form_frame,
            text="待办名称",
            bg=COLORS["card"],
            fg=COLORS["ink_soft"],
            font=(family, 8, "bold"),
        ).pack(anchor="w")
        self.title_entry = tk.Entry(
            self.form_frame,
            textvariable=self.title_var,
            font=(family, 11),
            bg=COLORS["warm"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
        )
        self.title_entry.pack(fill="x", ipady=7, pady=(5, 10))

        time_row = tk.Frame(self.form_frame, bg=COLORS["card"])
        time_row.pack(fill="x")
        time_row.grid_columnconfigure(0, weight=1)
        time_field = tk.Frame(time_row, bg=COLORS["card"])
        time_field.grid(row=0, column=0, sticky="ew")
        tk.Label(
            time_field,
            text="提醒时间（24 小时制）",
            bg=COLORS["card"],
            fg=COLORS["ink_soft"],
            font=(family, 8, "bold"),
        ).pack(anchor="w")
        self.time_entry = tk.Entry(
            time_field,
            textvariable=self.time_var,
            font=(family, 11),
            bg=COLORS["warm"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            width=9,
        )
        self.time_entry.pack(fill="x", ipady=7, pady=(5, 0))
        self.add_button = self.make_button(
            time_row, "添加待办", self.add_todo, kind="primary"
        )
        self.add_button.grid(row=0, column=1, sticky="sew", padx=(10, 0), pady=(20, 0))
        self.title_entry.bind("<Return>", lambda _event: self.time_entry.focus_set())
        self.time_entry.bind("<Return>", lambda _event: self.add_todo())

        self.form_hint = tk.Label(
            self.form_frame,
            text="",
            bg=COLORS["card"],
            fg=COLORS["accent_deep"],
            font=(family, 8),
            anchor="w",
            justify="left",
            wraplength=330,
        )
        self.form_hint.pack(fill="x", pady=(7, 0))

        tk.Frame(self.form_frame, height=1, bg=COLORS["line"]).pack(
            fill="x", pady=(13, 0)
        )

        list_head = tk.Frame(inner, bg=COLORS["card"])
        list_head.pack(fill="x", pady=(13, 8))
        tk.Label(
            list_head,
            text="当天待办",
            bg=COLORS["card"],
            fg=COLORS["ink"],
            font=(family, 9, "bold"),
        ).pack(side="left")
        tk.Label(
            list_head,
            text="按提醒时间排序",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(family, 8),
        ).pack(side="right")

        self.todo_scroll = ScrollableFrame(inner, COLORS["card"])
        self.todo_scroll.pack(fill="both", expand=True)

        tk.Label(
            inner,
            text="数据仅保存在本机。请保持程序运行，提醒才会准时弹出。",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=(family, 8),
            anchor="w",
            justify="left",
            wraplength=330,
        ).pack(fill="x", pady=(10, 0))

    def make_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        kind: str = "ghost",
    ) -> tk.Button:
        family = self.font_family
        if kind == "primary":
            options = {
                "bg": COLORS["accent"],
                "fg": COLORS["white"],
                "activebackground": COLORS["accent_deep"],
                "activeforeground": COLORS["white"],
                "font": (family, 10, "bold"),
                "padx": 15,
                "pady": 7,
                "relief": "flat",
                "bd": 0,
                "cursor": "hand2",
            }
        elif kind == "circle":
            options = {
                "bg": COLORS["card"],
                "fg": COLORS["ink_soft"],
                "activebackground": COLORS["accent_soft"],
                "activeforeground": COLORS["accent_deep"],
                "font": (family, 16),
                "width": 2,
                "height": 1,
                "relief": "flat",
                "bd": 0,
                "highlightthickness": 1,
                "highlightbackground": COLORS["line"],
                "cursor": "hand2",
            }
        else:
            options = {
                "bg": COLORS["warm"],
                "fg": COLORS["ink_soft"],
                "activebackground": COLORS["accent_soft"],
                "activeforeground": COLORS["accent_deep"],
                "font": (family, 9),
                "padx": 12,
                "pady": 6,
                "relief": "flat",
                "bd": 0,
                "highlightthickness": 1,
                "highlightbackground": COLORS["line_strong"],
                "cursor": "hand2",
            }
        return tk.Button(parent, text=text, command=command, **options)

    def _set_default_time(self) -> None:
        if self.selected_date != date.today():
            self.time_var.set("09:00")
            return
        next_hour = (datetime.now() + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        if next_hour.date() == date.today():
            self.time_var.set(next_hour.strftime("%H:%M"))
        else:
            self.time_var.set("23:59")

    def _refresh_all(self) -> None:
        self._refresh_calendar()
        self._refresh_panel()

    def _refresh_calendar(self) -> None:
        for child in self.calendar_grid.winfo_children():
            child.destroy()
        self._day_cells.clear()
        self.month_label.configure(text=f"{self.view_year}年{self.view_month}月")
        counts: dict[date, int] = {}
        for todo in self.todos:
            counts[todo.due_date] = counts.get(todo.due_date, 0) + 1
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.view_year, self.view_month
        )
        while len(weeks) < 6:
            last = weeks[-1][-1]
            weeks.append([last + timedelta(days=offset) for offset in range(1, 8)])
        today = date.today()
        for row, week in enumerate(weeks[:6]):
            for column, day in enumerate(week):
                cell = DayCell(self.calendar_grid, self, day, counts.get(day, 0))
                cell.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
                cell.set_state(
                    selected=day == self.selected_date,
                    today=day == today,
                )
                self._day_cells.append(cell)

    def _refresh_panel(self) -> None:
        self.selected_label.configure(text=format_date_cn(self.selected_date))
        selected_todos = todos_for_date(self.todos, self.selected_date)
        self.count_label.configure(text=f"{len(selected_todos)} 项")
        is_past = self.selected_date < date.today()
        self.add_button.configure(
            state=tk.DISABLED if is_past else tk.NORMAL,
            bg=COLORS["accent"] if not is_past else "#d7c9b8",
        )
        if is_past and not self.form_hint.cget("text"):
            self.form_hint.configure(text="过去日期不能新增提醒，请选择今天或之后的日期。")
        self._refresh_todo_list(selected_todos)

    def _refresh_todo_list(self, selected_todos: list[Todo]) -> None:
        for child in self.todo_scroll.inner.winfo_children():
            child.destroy()
        if not selected_todos:
            empty = tk.Frame(self.todo_scroll.inner, bg=COLORS["card"])
            empty.pack(fill="x", pady=(26, 12))
            tk.Label(
                empty,
                text="◷",
                bg=COLORS["card"],
                fg=COLORS["line_strong"],
                font=(self.font_family, 26),
            ).pack()
            message = (
                "这一天已经过去，没有待办。"
                if self.selected_date < date.today()
                else "这一天还没有待办，添加一个吧。"
            )
            tk.Label(
                empty,
                text=message,
                bg=COLORS["card"],
                fg=COLORS["muted"],
                font=(self.font_family, 9),
            ).pack(pady=(4, 0))
            return

        for todo in selected_todos:
            self._build_todo_row(todo)

    def _build_todo_row(self, todo: Todo) -> None:
        family = self.font_family
        row = tk.Frame(
            self.todo_scroll.inner,
            bg=COLORS["warm"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        row.pack(fill="x", pady=(0, 8))
        row.grid_columnconfigure(1, weight=1)
        tk.Label(
            row,
            text=format_time_text(todo.remind_time),
            bg=COLORS["warm"],
            fg=COLORS["accent_deep"],
            font=(family, 9, "bold"),
            width=7,
            anchor="w",
        ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(11, 6), pady=(10, 8))
        tk.Label(
            row,
            text=todo.title,
            bg=COLORS["warm"],
            fg=COLORS["ink"],
            font=(family, 9, "bold"),
            anchor="w",
            justify="left",
            wraplength=210,
        ).grid(row=0, column=1, sticky="ew", pady=(10, 0))
        meta = (
            f"已稍后至 {format_datetime_cn(todo.snoozed_until)}"
            if todo.snoozed_until
            else "等待提醒"
        )
        tk.Label(
            row,
            text=meta,
            bg=COLORS["warm"],
            fg=COLORS["green"] if todo.snoozed_until else COLORS["muted"],
            font=(family, 8),
            anchor="w",
            justify="left",
            wraplength=210,
        ).grid(row=1, column=1, sticky="ew", pady=(2, 9))
        tk.Button(
            row,
            text="删除",
            command=lambda item_id=todo.id: self.delete_todo(item_id),
            bg=COLORS["warm"],
            fg=COLORS["muted"],
            activebackground=COLORS["accent_soft"],
            activeforeground=COLORS["red"],
            font=(family, 8),
            relief="flat",
            bd=0,
            cursor="hand2",
        ).grid(row=0, column=2, rowspan=2, padx=(4, 8), pady=8)

    def select_date(self, selected: date) -> None:
        if selected == self.selected_date:
            return
        self.selected_date = selected
        self.view_year = selected.year
        self.view_month = selected.month
        self.form_hint.configure(text="", fg=COLORS["accent_deep"])
        self._set_default_time()
        self._refresh_all()

    def previous_month(self) -> None:
        year, month = self.view_year, self.view_month - 1
        if month == 0:
            year, month = year - 1, 12
        self.view_year, self.view_month = year, month
        self._refresh_calendar()

    def next_month(self) -> None:
        year, month = self.view_year, self.view_month + 1
        if month == 13:
            year, month = year + 1, 1
        self.view_year, self.view_month = year, month
        self._refresh_calendar()

    def go_today(self) -> None:
        self.selected_date = date.today()
        self.view_year = self.selected_date.year
        self.view_month = self.selected_date.month
        self.form_hint.configure(text="", fg=COLORS["accent_deep"])
        self._set_default_time()
        self._refresh_all()

    def add_todo(self) -> None:
        try:
            if self.selected_date < date.today():
                raise ValidationError("过去日期不能新增提醒，请选择今天或之后的日期。")
            title = self.title_var.get()
            remind_time = parse_time_text(self.time_var.get())
            due = combine_local(self.selected_date, remind_time)
            if due <= datetime.now():
                raise ValidationError("提醒时间需晚于当前时间。")
            todo = Todo.create(title, self.selected_date, remind_time)
        except ValidationError as exc:
            self._set_form_message(str(exc), error=True)
            return
        self.todos.append(todo)
        if not self._save_todos():
            self.todos.remove(todo)
            return
        self.title_var.set("")
        self._set_default_time()
        self._refresh_all()
        self._set_form_message(
            f"已添加，将在 {format_datetime_cn(todo.scheduled_at)} 提醒。"
        )
        self.title_entry.focus_set()
        self.check_for_due()

    def delete_todo(self, todo_id: str) -> None:
        todo = next((item for item in self.todos if item.id == todo_id), None)
        if todo is None:
            return
        if not messagebox.askyesno(
            "删除待办",
            f"确定删除“{todo.title}”吗？",
            parent=self.reminder_dialog.window if self.reminder_dialog else self.root,
        ):
            return
        self._remove_todo(todo, confirm=False)

    def cancel_todo(self, todo_id: str) -> bool:
        todo = next((item for item in self.todos if item.id == todo_id), None)
        if todo is None:
            return True
        return self._remove_todo(todo, confirm=False)

    def _remove_todo(self, todo: Todo, *, confirm: bool = True) -> bool:
        if confirm and not messagebox.askyesno(
            "删除待办", f"确定删除“{todo.title}”吗？", parent=self.root
        ):
            return False
        self.todos.remove(todo)
        if not self._save_todos():
            self.todos.append(todo)
            return False
        self._refresh_all()
        self._set_form_message("已删除待办。")
        return True

    def snooze_todo(self, todo_id: str, minutes: int) -> bool:
        todo = next((item for item in self.todos if item.id == todo_id), None)
        if todo is None:
            return True
        previous_until = todo.snoozed_until
        previous_count = todo.snooze_count
        try:
            todo.snooze(minutes)
        except ValidationError as exc:
            messagebox.showerror("稍后提醒", str(exc), parent=self._dialog_parent())
            return False
        if not self._save_todos():
            todo.snoozed_until = previous_until
            todo.snooze_count = previous_count
            return False
        self.settings.snooze_minutes = minutes
        try:
            self.settings_store.save(self.settings)
        except StorageError:
            pass
        self._refresh_all()
        return True

    def check_for_due(self) -> None:
        if self._closing or self.reminder_dialog is not None:
            return
        due = due_todos(self.todos, datetime.now())
        if due:
            self._show_reminder(due[0])

    def _show_reminder(self, todo: Todo) -> None:
        try:
            self.reminder_dialog = ReminderDialog(self, todo)
        except Exception:
            self._log_exception()
            messagebox.showerror(
                "提醒弹窗失败",
                "无法显示提醒弹窗，请查看程序日志。",
                parent=self.root,
            )

    def _tick(self) -> None:
        if self._closing:
            return
        try:
            self.check_for_due()
        finally:
            self.root.after(1000, self._tick)

    def _save_todos(self) -> bool:
        try:
            self.todo_store.save(self.todos)
            return True
        except StorageError as exc:
            messagebox.showerror(
                "保存失败", str(exc), parent=self._dialog_parent()
            )
            return False

    def _set_form_message(self, text: str, *, error: bool = False) -> None:
        self.form_hint.configure(
            text=text, fg=COLORS["red"] if error else COLORS["green"]
        )

    def _dialog_parent(self) -> tk.Misc:
        return self.reminder_dialog.window if self.reminder_dialog else self.root

    def _on_close(self) -> None:
        if self.reminder_dialog is not None:
            self.reminder_dialog.bring_to_front()
            return
        self._closing = True
        try:
            for after_id in self.root.tk.splitlist(self.root.tk.call("after", "info")):
                self.root.after_cancel(after_id)
        except tk.TclError:
            pass
        self.root.destroy()

    def _log_exception(self) -> None:
        try:
            self.paths.data_dir.mkdir(parents=True, exist_ok=True)
            with (self.paths.data_dir / "schedule_reminder.log").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(datetime.now().isoformat(timespec="seconds") + "\n")
                traceback.print_exc(file=handle)
                handle.write("\n")
        except OSError:
            pass

    def _report_callback_exception(self, _exc, _value, _tb) -> None:
        self._log_exception()
        messagebox.showerror(
            "程序错误",
            "程序遇到一个错误，详情已写入本地日志。",
            parent=self.root,
        )


def _single_instance() -> bool:
    """Keep two copies from ringing the same reminders at once."""
    global _MUTEX_HANDLE
    if os.name != "nt" or os.environ.get("SCHEDULE_REMINDER_ALLOW_MULTI") == "1":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_wchar_p,
        ]
        handle = kernel32.CreateMutexW(None, False, "Local\\ScheduleReminderDesktop")
        if not handle:
            return True
        if ctypes.get_last_error() == 183:
            ctypes.windll.user32.MessageBoxW(
                None,
                "日程提醒已经在运行。",
                APP_NAME,
                0x40,
            )
            kernel32.CloseHandle(handle)
            return False
        _MUTEX_HANDLE = handle
        return True
    except (AttributeError, OSError):
        return True


def run() -> None:
    if not _single_instance():
        return
    root = tk.Tk()
    app = ScheduleReminderApp(root)
    try:
        root.mainloop()
    finally:
        if _MUTEX_HANDLE:
            try:
                ctypes.windll.kernel32.CloseHandle(_MUTEX_HANDLE)
            except (AttributeError, OSError):
                pass
