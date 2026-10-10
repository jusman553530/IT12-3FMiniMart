# ─────────────────────────────────────────────
# PURCHASE RECORDS VIEW
# ─────────────────────────────────────────────
from views.receive_dialog import ReceiveConfirmDialog
from views.purchase_order_dialog import PurchaseOrderDialog
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timedelta

from controllers.purchase_controller import PurchaseController
from controllers.supplier_controller import SupplierController
from controllers.inventory_controller import InventoryController
from views.date_picker import DatePickerField
from utils import prepare_dialog_screen, ui_date_to_db, is_valid_ui_date
from utils_pkg.purchase_pdf_export import export_purchase_pdf
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_INPUT, BG_ROW_ALT, BORDER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    BRAND_GREEN, BRAND_YELLOW,
    ACCENT, ACCENT_HOVER, SUCCESS, DANGER, DANGER_HOVER,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


class PurchaseView(ctk.CTkFrame):

    PAGE_SIZE = 10

    def __init__(self, parent, user):
        super().__init__(parent, fg_color=BG_MAIN)
        self.user = user
        self.filter_status = "All"
        self.search_query = ""
        self.date_from = ""
        self.date_to = ""

        self.active_range_button = None
        self._programmatic_set = False

        self.current_page = 1
        self.total_pages = 1

        self._build()
        self._load()

    # ─────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────

    def _build(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(title_box, text="Purchase Records",
                     font=font_bold(22),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(title_box,
                     text="Track purchase orders and received stock",
                     font=font(11),
                     text_color=FG_SECONDARY,
                     anchor="w").pack(fill="x", pady=(2, 0))

        ctk.CTkButton(header_frame, text="+ New Purchase Order",
                      height=38, corner_radius=8,
                      font=font_bold(12),
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._new_po_dialog).pack(side="right")

        filter_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                   corner_radius=12,
                                   border_width=1,
                                   border_color=BORDER)
        filter_card.pack(fill="x", padx=20, pady=(0, 10))

        # ---- Row 1 ----
        row1 = ctk.CTkFrame(filter_card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(row1, text="Search",
                     font=font_bold(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=(0, 10))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self.search_e = ctk.CTkEntry(
            row1,
            placeholder_text="Search by PO #, supplier, ordered by, notes...",
            textvariable=self.search_var,
            width=360, height=36,
            corner_radius=8,
            font=font(12),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
        )
        self.search_e.pack(side="left", padx=(0, 8))

        ctk.CTkButton(row1, text="✕", width=36, height=36,
                      corner_radius=8,
                      font=font(13),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._clear_search).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row1, text="Status",
                     font=font_bold(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=(0, 8))

        self.status_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            row1,
            values=["All", "Ordered", "Received", "Cancelled"],
            variable=self.status_var,
            width=150, height=36,
            corner_radius=8,
            font=font(12),
            fg_color=BG_INPUT,
            button_color=BG_INPUT,
            button_hover_color=NEUTRAL,
            text_color=FG_PRIMARY,
            command=self._on_status_change,
        ).pack(side="left", padx=(0, 20))

        ctk.CTkButton(row1, text="Refresh", width=100, height=36,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._load).pack(side="right")

        # ---- Row 2: date range (DatePickerField) ----
        row2 = ctk.CTkFrame(filter_card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(row2, text="Date From",
                     font=font_bold(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=(0, 8))

        self.date_from_var = ctk.StringVar()
        self.date_from_var.trace_add("write", self._on_date_change)

        self.date_from_e = DatePickerField(
            row2,
            textvariable=self.date_from_var,
            width=180, height=36,
        )
        self.date_from_e.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row2, text="Date To",
                     font=font_bold(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=(0, 8))

        self.date_to_var = ctk.StringVar()
        self.date_to_var.trace_add("write", self._on_date_change)

        self.date_to_e = DatePickerField(
            row2,
            textvariable=self.date_to_var,
            width=180, height=36,
        )
        self.date_to_e.pack(side="left", padx=(0, 16))

        self.btn_today = ctk.CTkButton(
            row2, text="Today", width=80, height=36,
            corner_radius=8,
            font=font(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=self._range_today,
        )
        self.btn_today.pack(side="left", padx=2)

        self.btn_7days = ctk.CTkButton(
            row2, text="Last 7 Days", width=100, height=36,
            corner_radius=8,
            font=font(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=self._range_7_days,
        )
        self.btn_7days.pack(side="left", padx=2)

        self.btn_month = ctk.CTkButton(
            row2, text="This Month", width=100, height=36,
            corner_radius=8,
            font=font(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=self._range_this_month,
        )
        self.btn_month.pack(side="left", padx=2)

        self.btn_clear = ctk.CTkButton(
            row2, text="Clear Dates", width=100, height=36,
            corner_radius=8,
            font=font(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=self._clear_dates,
        )
        self.btn_clear.pack(side="left", padx=2)

        self.count_label = ctk.CTkLabel(row2, text="",
                                        font=font_bold(11),
                                        text_color=FG_SECONDARY)
        self.count_label.pack(side="right", padx=(0, 4))

        # ---- List card ----
        list_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                 corner_radius=12,
                                 border_width=1,
                                 border_color=BORDER)
        list_card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.list_frame = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=8)

        pager = ctk.CTkFrame(list_card, fg_color="transparent")
        pager.pack(fill="x", padx=12, pady=(0, 12))

        self.prev_btn = ctk.CTkButton(
            pager, text="‹ Prev",
            width=90, height=32,
            corner_radius=8,
            font=font_bold(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=lambda: self._change_page(-1),
        )
        self.prev_btn.pack(side="left")

        self.page_label = ctk.CTkLabel(
            pager, text="Page 1 of 1",
            font=font_bold(11),
            text_color=FG_SECONDARY,
        )
        self.page_label.pack(side="left", fill="x", expand=True)

        self.next_btn = ctk.CTkButton(
            pager, text="Next ›",
            width=90, height=32,
            corner_radius=8,
            font=font_bold(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=lambda: self._change_page(+1),
        )
        self.next_btn.pack(side="right")

    # ─────────────────────────────────────────────
    # PAGINATION
    # ─────────────────────────────────────────────

    def _change_page(self, delta):
        new_page = self.current_page + delta
        if 1 <= new_page <= self.total_pages:
            self.current_page = new_page
            self._load()

    def _update_pager(self):
        self.page_label.configure(
            text=f"Page {self.current_page} of {self.total_pages}"
        )

        if self.current_page <= 1:
            self.prev_btn.configure(
                state="disabled",
                fg_color=BG_INPUT,
                text_color=FG_MUTED,
            )
        else:
            self.prev_btn.configure(
                state="normal",
                fg_color=NEUTRAL,
                text_color=NEUTRAL_TEXT,
            )

        if self.current_page >= self.total_pages:
            self.next_btn.configure(
                state="disabled",
                fg_color=BG_INPUT,
                text_color=FG_MUTED,
            )
        else:
            self.next_btn.configure(
                state="normal",
                fg_color=NEUTRAL,
                text_color=NEUTRAL_TEXT,
            )

    # ─────────────────────────────────────────────
    # FILTERS
    # ─────────────────────────────────────────────

    def _on_search_change(self, *args):
        self.search_query = self.search_var.get().strip().lower()
        self.current_page = 1
        self._load()

    def _clear_search(self):
        self.search_var.set("")

    def _on_status_change(self, choice):
        self.filter_status = choice
        self.current_page = 1
        self._load()

    def _highlight_button(self, button):
        if self.active_range_button is not None:
            self.active_range_button.configure(
                fg_color=NEUTRAL, text_color=NEUTRAL_TEXT,
            )
        if button is not None:
            button.configure(fg_color=ACCENT, text_color="#FFFFFF")
        self.active_range_button = button

    def _clear_button_highlight(self):
        if self.active_range_button is not None:
            self.active_range_button.configure(
                fg_color=NEUTRAL, text_color=NEUTRAL_TEXT,
            )
        self.active_range_button = None

    def _on_date_change(self, *args):
        if self._programmatic_set:
            return

        d_from = self.date_from_var.get().strip()
        d_to = self.date_to_var.get().strip()

        if d_from and len(d_from) < 10:
            return
        if d_to and len(d_to) < 10:
            return
        if d_from and not is_valid_ui_date(d_from):
            return
        if d_to and not is_valid_ui_date(d_to):
            return
        if d_from and d_to and d_from > d_to:
            return

        self._clear_button_highlight()
        self.date_from = d_from
        self.date_to = d_to
        self.current_page = 1
        self._load()

    def _range_today(self):
        today = datetime.now().strftime("%m/%d/%Y")
        self._set_dates_programmatically(today, today, self.btn_today)

    def _range_7_days(self):
        today = datetime.now()
        start = (today - timedelta(days=6)).strftime("%m/%d/%Y")
        end = today.strftime("%m/%d/%Y")
        self._set_dates_programmatically(start, end, self.btn_7days)

    def _range_this_month(self):
        today = datetime.now()
        start = today.replace(day=1).strftime("%m/%d/%Y")
        end = today.strftime("%m/%d/%Y")
        self._set_dates_programmatically(start, end, self.btn_month)

    def _clear_dates(self):
        self._set_dates_programmatically("", "", self.btn_clear)

    def _set_dates_programmatically(self, d_from, d_to, button):
        self._programmatic_set = True
        self.date_from_var.set(d_from)
        self.date_to_var.set(d_to)
        self._programmatic_set = False

        self.date_from = d_from
        self.date_to = d_to
        self.current_page = 1
        self._highlight_button(button)
        self._load()

    # ─────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────

    def _load(self):
        if self.filter_status == "All":
            purchases = PurchaseController.list_all()
        else:
            purchases = PurchaseController.list_by_status(self.filter_status)

        purchases = self._filter_by_date(purchases)

        if self.search_query:
            purchases = [p for p in purchases if self._matches_search(p)]

        self._render(purchases)

    def _filter_by_date(self, purchases):
        if not self.date_from and not self.date_to:
            return purchases

        db_from = ui_date_to_db(self.date_from)
        db_to = ui_date_to_db(self.date_to)

        result = []
        for p in purchases:
            created = (p["created_at"] or "")[:10]
            if db_from and created < db_from:
                continue
            if db_to and created > db_to:
                continue
            result.append(p)
        return result

    def _matches_search(self, p):
        q = self.search_query
        fields = [
            f"#{p['purchase_id']}",
            str(p["purchase_id"]),
            (p["supplier_name"] or "").lower(),
            (p["full_name"] or "").lower(),
            (p["username"] or "").lower(),
            (p["status"] or "").lower(),
            (p["notes"] or "").lower(),
        ]
        return any(q in f for f in fields)

    # ─────────────────────────────────────────────
    # RENDER
    # ─────────────────────────────────────────────

    def _render(self, purchases):
        for w in self.list_frame.winfo_children():
            w.destroy()

        total = len(purchases)
        self.count_label.configure(text=f"{total} record(s)")

        self.total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages

        start = (self.current_page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_purchases = purchases[start:end]

        header = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header.pack(fill="x", pady=(4, 8))
        cols = [
            ("PO #",          70),
            ("Supplier",      170),
            ("Total",         90),
            ("Status",        100),
            ("Ordered By",    120),
            ("Date Ordered",  130),
            ("Date Received", 130),
        ]
        for text, width in cols:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        if not page_purchases:
            ctk.CTkLabel(self.list_frame,
                         text="No records match your filters.",
                         font=font(12),
                         text_color=FG_MUTED).pack(pady=30)
            self._update_pager()
            return

        for i, p in enumerate(page_purchases):
            self._render_row(p, i)

        self._update_pager()

    def _render_row(self, p, index=0):
        bg = BG_ROW_ALT if index % 2 else BG_CARD

        row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=6)
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(row, text=f"#{p['purchase_id']}",
                     width=70, anchor="w",
                     font=font_bold(11),
                     text_color=ACCENT).pack(side="left", padx=3, pady=6)

        ctk.CTkLabel(row, text=p["supplier_name"] or "-",
                     width=170, anchor="w",
                     font=font(11),
                     text_color=FG_PRIMARY).pack(side="left", padx=3)

        # ---- Total (reads purchases.total_cost) ----
        try:
            total_val = float(p["total_cost"] or 0)
        except (TypeError, ValueError):
            total_val = 0.0

        ctk.CTkLabel(row, text=f"₱{total_val:.2f}",
                     width=90, anchor="w",
                     font=font_bold(11),
                     text_color=FG_PRIMARY).pack(side="left", padx=3)

        status = p["status"]
        colors = {
            "Ordered":   BRAND_YELLOW,
            "Received":  BRAND_GREEN,
            "Cancelled": DANGER,
        }
        ctk.CTkLabel(row, text=status, width=100, anchor="w",
                     font=font_bold(11),
                     text_color=colors.get(status, FG_SECONDARY)
                     ).pack(side="left", padx=3)

        ctk.CTkLabel(row, text=p["full_name"] or p["username"] or "-",
                     width=120, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        ctk.CTkLabel(row, text=(p["created_at"] or "")[:10],
                     width=130, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        ctk.CTkLabel(row, text=(p["received_at"] or "-")[:10],
                     width=130, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=4)

        ctk.CTkButton(actions, text="View", width=60, height=28,
                      corner_radius=6,
                      font=font_bold(11),
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda pur=p: self._view_dialog(pur)
                      ).pack(side="left", padx=2)

        if status == "Ordered":
            ctk.CTkButton(actions, text="Receive", width=70, height=28,
                          corner_radius=6,
                          font=font_bold(11),
                          fg_color=BRAND_GREEN, hover_color="#1E9040",
                          command=lambda pur=p: self._receive(pur)
                          ).pack(side="left", padx=2)

            ctk.CTkButton(actions, text="Cancel", width=70, height=28,
                          corner_radius=6,
                          font=font_bold(11),
                          fg_color=DANGER, hover_color=DANGER_HOVER,
                          command=lambda pur=p: self._cancel(pur)
                          ).pack(side="left", padx=2)

    # ─────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────

    def _receive(self, purchase):
        items = PurchaseController.get_items(purchase["purchase_id"])
        dialog = ReceiveConfirmDialog(
            self.winfo_toplevel(),
            purchase,
            items,
        )
        # ⚡ Caller blocks here. The dialog does NOT block on construction.
        dialog.wait_window()

        if not dialog.confirmed:
            return

        received = dialog.received_quantities
        if not received:
            return

        ok, msg = PurchaseController.receive(
            self.user,
            purchase["purchase_id"],
            received_quantities=received,
            line_costs=dialog.line_costs,
            total_amount=dialog.total_amount,
        )
        if ok:
            messagebox.showinfo("Received", msg)
            self._load()
        else:
            messagebox.showerror("Error", msg)

    def _cancel(self, purchase):
        confirm = messagebox.askyesno(
            "Cancel Purchase Order",
            f"Cancel PO #{purchase['purchase_id']}?"
        )
        if not confirm:
            return

        ok, msg = PurchaseController.cancel(self.user, purchase["purchase_id"])
        if ok:
            self._load()
        else:
            messagebox.showerror("Error", msg)

    # ─────────────────────────────────────────────
    # DIALOGS
    # ─────────────────────────────────────────────

    def _new_po_dialog(self):
        PurchaseOrderDialog(self.winfo_toplevel(), self.user, on_save=self._load)

    def _view_dialog(self, purchase):
        PurchaseDetailDialog(self.winfo_toplevel(), purchase)


# ─────────────────────────────────────────────
# PURCHASE DETAIL DIALOG
# ─────────────────────────────────────────────

class PurchaseDetailDialog(ctk.CTkToplevel):

    def __init__(self, parent, purchase):
        super().__init__(parent)
        self.parent = parent
        self.purchase = purchase
        self.title(f"PO #{purchase['purchase_id']}")
        self.geometry("740x660")
        self.minsize(680, 580)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)
        self._build()
        prepare_dialog_screen(self, self.parent)

    def _build(self):
        p = self.purchase

        ctk.CTkLabel(self, text=f"Purchase Order #{p['purchase_id']}",
                     font=font_bold(18),
                     text_color=FG_PRIMARY).pack(pady=(18, 4))

        ctk.CTkLabel(self,
                     text=p["supplier_name"] or "Unknown Supplier",
                     font=font(12),
                     text_color=FG_SECONDARY).pack(pady=(0, 14))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=20, pady=(8, 16))

        ctk.CTkButton(btn_row, text="Export PDF",
                      width=140, height=38,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=self._export_pdf).pack(side="left")

        ctk.CTkButton(btn_row, text="Close",
                      width=120, height=38,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self.destroy).pack(side="right")

        info = ctk.CTkFrame(self, fg_color=BG_CARD,
                            corner_radius=12,
                            border_width=1,
                            border_color=BORDER)
        info.pack(fill="x", padx=20, pady=(0, 10))

        # ⚡ Total still reads purchases.total_cost (user-entered at receive)
        try:
            total_val = float(p["total_cost"] or 0)
        except (TypeError, ValueError):
            total_val = 0.0

        rows = [
            ("Status",        p["status"]),
            ("Total",         f"₱{total_val:.2f}"),
            ("Ordered By",    p["full_name"] or p["username"]),
            ("Date Ordered",  p["created_at"]),
            ("Date Received", p["received_at"] or "-"),
            ("Notes",         p["notes"] or "-"),
        ]
        for i, (label, value) in enumerate(rows):
            if i > 0:
                ctk.CTkFrame(info, height=1, fg_color=BORDER).pack(
                    fill="x", padx=14)

            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=8)

            ctk.CTkLabel(row, text=label,
                         width=120, anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left")

            ctk.CTkLabel(row, text=str(value), anchor="w",
                         font=font(12),
                         text_color=FG_PRIMARY).pack(side="left")

        items_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                  corner_radius=12,
                                  border_width=1,
                                  border_color=BORDER)
        items_card.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        ctk.CTkLabel(items_card, text="Items",
                     font=font_bold(13),
                     text_color=FG_PRIMARY).pack(pady=(12, 4))

        lines = ctk.CTkScrollableFrame(items_card, fg_color="transparent")
        lines.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ⚡ Cost / Subtotal columns removed — no longer meaningful
        header = ctk.CTkFrame(lines, fg_color="transparent")
        header.pack(fill="x", pady=(4, 8))
        for text, width in [("Code", 90), ("Name", 280),
                            ("Ordered", 80), ("Received", 80)]:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        items = PurchaseController.get_items(p["purchase_id"])
        for i, it in enumerate(items):
            bg = BG_ROW_ALT if i % 2 else BG_CARD

            row = ctk.CTkFrame(lines, fg_color=bg, corner_radius=6)
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=it["product_code"] or "-",
                         width=90, anchor="w",
                         font=font(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3, pady=6)

            # ⚡ Name joined with size
            name_parts = [it["product_name"]]
            size = it["product_size"] if "product_size" in it.keys() else None
            if size:
                name_parts.append(size)
            display_name = " | ".join(p for p in name_parts if p)

            ctk.CTkLabel(row, text=display_name,
                         width=280, anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3)

            ctk.CTkLabel(row, text=str(it["quantity"]),
                         width=80, anchor="w",
                         font=font(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3)

            recv = it["received_quantity"]
            recv_text = "-" if recv is None else str(recv)
            recv_color = FG_MUTED if recv is None else BRAND_GREEN

            ctk.CTkLabel(row, text=recv_text,
                         width=80, anchor="w",
                         font=font_bold(11),
                         text_color=recv_color).pack(side="left", padx=3)

    def _export_pdf(self):
        p = self.purchase
        items = PurchaseController.get_items(p["purchase_id"])

        purchase_dict = dict(p) if not isinstance(p, dict) else p
        items_list = [
            dict(it) if not isinstance(it, dict) else it
            for it in items
        ]

        ok, result = export_purchase_pdf(
            purchase=purchase_dict,
            items=items_list,
            parent_window=self.winfo_toplevel(),
        )

        if ok:
            messagebox.showinfo("Export Complete",
                                f"PDF saved to:\n{result}")
        elif result != "Cancelled.":
            messagebox.showerror("Export Failed", result)