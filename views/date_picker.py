# ─────────────────────────────────────────────
# DATE PICKER FIELD (CTk-styled)
# ─────────────────────────────────────────────

from datetime import datetime
import customtkinter as ctk
from tkcalendar import Calendar

from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_INPUT, BORDER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    BRAND_GREEN,
    ACCENT, ACCENT_HOVER,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


class DatePickerField(ctk.CTkFrame):

    def __init__(self, parent, textvariable=None, width=180, height=36,
                 placeholder="MM/DD/YYYY"):
        super().__init__(parent, fg_color="transparent",
                         width=width, height=height)

        self.var = textvariable or ctk.StringVar()
        self._placeholder = placeholder

        # Entry (left side)
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.var,
            height=height,
            width=width - 44,
            corner_radius=8,
            font=font(11),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            placeholder_text=placeholder,
        )
        self.entry.pack(side="left", padx=(0, 4))

        # Calendar button (right side)
        self.btn = ctk.CTkButton(
            self,
            text="📅",
            width=36,
            height=height,
            corner_radius=8,
            font=("Segoe UI Emoji", 14),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._open_picker,
        )
        self.btn.pack(side="left")

    def _open_picker(self):
        initial = None
        try:
            initial = datetime.strptime(self.var.get().strip(), "%m/%d/%Y").date()
        except (ValueError, TypeError):
            initial = datetime.now().date()

        DatePickerPopup(
            parent=self.winfo_toplevel(),
            anchor_widget=self,
            initial_date=initial,
            on_pick=self._on_pick,
        )

    def _on_pick(self, picked_date):
        if picked_date is None:
            self.var.set("")
        else:
            self.var.set(picked_date.strftime("%m/%d/%Y"))


# ─────────────────────────────────────────────
# POPUP
# ─────────────────────────────────────────────

class DatePickerPopup(ctk.CTkToplevel):

    def __init__(self, parent, anchor_widget, initial_date, on_pick):
        super().__init__(parent)
        self.parent = parent
        self.anchor_widget = anchor_widget
        self.on_pick = on_pick

        self.title("Pick a date")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        self.cal = Calendar(
            self,
            selectmode="day",
            year=initial_date.year,
            month=initial_date.month,
            day=initial_date.day,
            date_pattern="mm/dd/yyyy",
            showweeknumbers=False,
            weekendbackground="#F8FAFC",
            weekendforeground=FG_PRIMARY,
            othermonthbackground="#F1F5F9",
            othermonthforeground=FG_MUTED,
            othermonthwebackground="#F1F5F9",
            othermonthweforeground=FG_MUTED,
            headersbackground=ACCENT,
            headersforeground="white",
            selectbackground=BRAND_GREEN,
            selectforeground="white",
            normalbackground="white",
            normalforeground=FG_PRIMARY,
            bordercolor=BORDER,
            background=BG_CARD,
            foreground=FG_PRIMARY,
            font=("Segoe UI", 11),
        )
        self.cal.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(btn_row, text="Today", width=80, height=32,
                      corner_radius=8, font=font_bold(11),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._pick_today).pack(side="left")

        ctk.CTkButton(btn_row, text="Clear", width=80, height=32,
                      corner_radius=8, font=font_bold(11),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._clear).pack(side="left", padx=(6, 0))

        ctk.CTkButton(btn_row, text="Select", width=90, height=32,
                      corner_radius=8, font=font_bold(11),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=self._select).pack(side="right")

        self.update_idletasks()
        self._position_below_anchor()

        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self.bind("<Escape>", lambda e: self.destroy())

    def _position_below_anchor(self):
        self.update_idletasks()

        anchor = self.anchor_widget
        ax = anchor.winfo_rootx()
        ay = anchor.winfo_rooty()
        ah = anchor.winfo_height()

        popup_w = self.winfo_reqwidth()
        popup_h = self.winfo_reqheight()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        x = ax
        y = ay + ah + 4

        if x + popup_w > screen_w:
            x = screen_w - popup_w - 10
        if y + popup_h > screen_h:
            y = ay - popup_h - 4
        if x < 0:
            x = 0
        if y < 0:
            y = 0

        self.geometry(f"{popup_w}x{popup_h}+{x}+{y}")

    def _pick_today(self):
        today = datetime.now().date()
        self.cal.selection_set(today)

    def _clear(self):
        self.on_pick(None)
        self.destroy()

    def _select(self):
        try:
            picked = self.cal.selection_get()
        except Exception:
            picked = datetime.now().date()
        self.on_pick(picked)
        self.destroy()