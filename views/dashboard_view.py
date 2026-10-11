# ─────────────────────────────────────────────
# DASHBOARD VIEW (KPIs + Expiring Soon + Low Stock)
# ─────────────────────────────────────────────

from datetime import datetime
import customtkinter as ctk

from controllers.dashboard_controller import DashboardController
from controllers.inventory_controller import InventoryController
from controllers.auth_controller import AuthController
from controllers.transaction_controller import TransactionController
from views.transaction_dialogs import TransactionDetailDialog
from utils import center_on_parent
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_INPUT, BG_ROW_ALT, BORDER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    BRAND_GREEN, BRAND_YELLOW,
    ACCENT, ACCENT_HOVER, SUCCESS, DANGER, DANGER_HOVER,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


class DashboardView(ctk.CTkFrame):

    PAGE_SIZE = 6

    def __init__(self, parent, user):
        super().__init__(parent, fg_color=BG_MAIN)
        self.user = user
        self.on_navigate = None

        self.lowstock_page = 1
        self.lowstock_total_pages = 1

        self.expiring_page = 1
        self.expiring_total_pages = 1

        # Snapshot of the last stats fetch
        self._stats = {}

        # ⚡ Reusable Today's Sales popup (created lazily on first click)
        self._sales_dialog = None

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

        ctk.CTkLabel(title_box,
                     text=f"Welcome back, {self.user['full_name']}",
                     font=font_bold(22),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(title_box,
                     text="Here's an overview of your store today",
                     font=font(11),
                     text_color=FG_SECONDARY,
                     anchor="w").pack(fill="x", pady=(2, 0))

        # ═════════════════════════════════════════
        # KPI ROW
        # ═════════════════════════════════════════

        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.pack(fill="x", padx=20, pady=(0, 10))

        self.sales_card = self._make_kpi_card(
            kpi_row, "TODAY'S SALES", "₱0.00", ACCENT,
            command=self._on_sales_click,
        )
        self.txn_card = self._make_kpi_card(
            kpi_row, "TRANSACTIONS", "0", FG_PRIMARY,
            command=self._go_to_transactions,
        )
        self.lowstock_card = self._make_kpi_card(
            kpi_row, "LOW STOCK", "0", "#D97706",
            command=self._go_to_inventory_low,
        )
        self.expiring_card = self._make_kpi_card(
            kpi_row, "EXPIRING SOON", "0", "#D97706",
            command=self._go_to_inventory_expiring,
        )

        # ═════════════════════════════════════════
        # TWO PANELS
        # ═════════════════════════════════════════

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        expiring_panel = ctk.CTkFrame(body, fg_color=BG_CARD,
                                      corner_radius=12,
                                      border_width=1,
                                      border_color=BORDER)
        expiring_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        exp_header = ctk.CTkFrame(expiring_panel, fg_color="transparent")
        exp_header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(exp_header, text="Expiring in 30 Days",
                     font=font_bold(14),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(side="left")

        ctk.CTkButton(exp_header, text="View All",
                      width=90, height=30,
                      corner_radius=8,
                      font=font_bold(11),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._go_to_inventory_expiring
                      ).pack(side="right")

        self.expiring_frame = ctk.CTkScrollableFrame(expiring_panel,
                                                     fg_color="transparent")
        self.expiring_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self.expiring_pager = self._make_pager(expiring_panel, "expiring")

        right = ctk.CTkFrame(body, fg_color=BG_CARD,
                             corner_radius=12,
                             border_width=1,
                             border_color=BORDER)
        right.pack(side="right", fill="both", expand=True)

        right_header = ctk.CTkFrame(right, fg_color="transparent")
        right_header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(right_header, text="Low Stock Alerts",
                     font=font_bold(14),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(side="left")

        ctk.CTkButton(right_header, text="View All",
                      width=90, height=30,
                      corner_radius=8,
                      font=font_bold(11),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._go_to_inventory_low
                      ).pack(side="right")

        self.lowstock_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.lowstock_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self.lowstock_pager = self._make_pager(right, "lowstock")

    # ─────────────────────────────────────────────
    # KPI CARD
    # ─────────────────────────────────────────────

    def _make_kpi_card(self, parent, label, value, value_color, command):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD,
                            corner_radius=12,
                            border_width=1,
                            border_color=BORDER,
                            height=100)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        label_widget = ctk.CTkLabel(inner, text=label,
                                    font=font_bold(10),
                                    text_color=FG_SECONDARY,
                                    anchor="nw")
        label_widget.pack(fill="x", anchor="nw")

        value_label = ctk.CTkLabel(inner, text=value,
                                   font=font_bold(24),
                                   text_color=value_color,
                                   anchor="se",
                                   justify="right")
        value_label.pack(side="bottom", anchor="e", fill="x")

        for w in (card, inner, label_widget, value_label):
            w.bind("<Button-1>", lambda e: command())
            w.bind("<Enter>", lambda e, c=card:
                   c.configure(fg_color="#EAF0FF"))
            w.bind("<Leave>", lambda e, c=card:
                   c.configure(fg_color=BG_CARD))
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

        return value_label

    # ─────────────────────────────────────────────
    # PAGER
    # ─────────────────────────────────────────────

    def _make_pager(self, parent, pager_key):
        pager = ctk.CTkFrame(parent, fg_color="transparent")
        pager.pack(fill="x", padx=12, pady=(0, 12))

        prev_btn = ctk.CTkButton(
            pager, text="‹ Prev",
            width=80, height=30,
            corner_radius=8,
            font=font_bold(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=lambda: self._change_page(pager_key, -1),
        )
        prev_btn.pack(side="left")

        page_label = ctk.CTkLabel(pager, text="Page 1 of 1",
                                  font=font_bold(11),
                                  text_color=FG_SECONDARY)
        page_label.pack(side="left", fill="x", expand=True)

        next_btn = ctk.CTkButton(
            pager, text="Next ›",
            width=80, height=30,
            corner_radius=8,
            font=font_bold(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=lambda: self._change_page(pager_key, +1),
        )
        next_btn.pack(side="right")

        return {"prev": prev_btn, "next": next_btn, "label": page_label}

    def _change_page(self, pager_key, delta):
        if pager_key == "lowstock":
            new_page = self.lowstock_page + delta
            if 1 <= new_page <= self.lowstock_total_pages:
                self.lowstock_page = new_page
                self._render_low_stock()
        elif pager_key == "expiring":
            new_page = self.expiring_page + delta
            if 1 <= new_page <= self.expiring_total_pages:
                self.expiring_page = new_page
                self._render_expiring()

    # ─────────────────────────────────────────────
    # NAVIGATION
    # ─────────────────────────────────────────────

    def _on_sales_click(self):
        # ⚡ Reuse one Today's Sales popup for the whole session
        if self._sales_dialog is None or \
           not self._sales_dialog.winfo_exists():
            self._sales_dialog = TodaySalesDialog(
                parent=self.winfo_toplevel(),
                stats=self._stats,
            )
        else:
            self._sales_dialog.load(stats=self._stats)
        self._sales_dialog.deiconify()

    def _go_to_transactions(self):
        if callable(self.on_navigate):
            self.on_navigate("sales")

    def _go_to_inventory_low(self):
        if callable(self.on_navigate):
            self.on_navigate("inventory", initial_filter="low")

    def _go_to_inventory_expiring(self):
        if callable(self.on_navigate):
            self.on_navigate("inventory", initial_filter="expiring")

    # ─────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────

    def _load(self):
        try:
            stats = DashboardController.get_stats()
        except Exception as e:
            import traceback
            print(f"[Dashboard] get_stats failed: {e}")
            traceback.print_exc()
            stats = {}

        self._stats = stats or {}

        self.sales_card.configure(
            text=f"₱{stats.get('total_sales_today', 0):,.2f}"
        )
        self.txn_card.configure(
            text=f"{stats.get('txn_count_today', 0):,}"
        )

        low_count = stats.get("low_stock_count", 0)
        self.lowstock_card.configure(
            text=f"{low_count:,}",
            text_color=("#D97706" if low_count > 0 else FG_PRIMARY),
        )

        expiring = stats.get("expiring_soon_count", 0)
        expired = stats.get("expired_count", 0)
        self.expiring_card.configure(
            text=f"{expiring:,}",
            text_color=(DANGER if expired > 0 else
                        "#D97706" if expiring > 0 else FG_PRIMARY),
        )

        self._render_expiring()
        self._render_low_stock()

    # ─────────────────────────────────────────────
    # EXPIRING SOON
    # ─────────────────────────────────────────────

    def _render_expiring(self):
        for w in self.expiring_frame.winfo_children():
            w.destroy()

        rows = []
        expired = []

        try:
            rows = list(InventoryController.list_expiring_soon(days=30))
        except Exception as e:
            print(f"[Dashboard] list_expiring_soon failed: {e}")

        try:
            expired = list(InventoryController.list_expired_batches())
        except Exception as e:
            print(f"[Dashboard] list_expired_batches failed: {e}")

        seen_keys = set()
        combined = []

        for r in expired:
            key = (r.get("batch_id"), r.get("product_id"))
            if key not in seen_keys:
                seen_keys.add(key)
                combined.append(dict(r))

        for r in rows:
            key = (r.get("batch_id"), r.get("product_id"))
            if key not in seen_keys:
                seen_keys.add(key)
                combined.append(dict(r))

        total = len(combined)
        self.expiring_total_pages = max(
            1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        )
        if self.expiring_page > self.expiring_total_pages:
            self.expiring_page = self.expiring_total_pages

        start = (self.expiring_page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_rows = combined[start:end]

        if not page_rows:
            ctk.CTkLabel(self.expiring_frame,
                         text="No products expiring in the next 30 days.",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=30)
            self._update_pager(self.expiring_pager, 1, 1)
            return

        header = ctk.CTkFrame(self.expiring_frame, fg_color="transparent")
        header.pack(fill="x", pady=(4, 8))

        for text, width in [
            ("Product",    180),
            ("Batch No",   130),
            ("Qty",         50),
            ("Expires",    130),
        ]:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        today = datetime.now().date()

        for i, b in enumerate(page_rows):
            bg = BG_ROW_ALT if i % 2 else BG_CARD
            row = ctk.CTkFrame(self.expiring_frame, fg_color=bg, corner_radius=6)
            row.pack(fill="x", pady=2)

            display = " ".join(
                part for part in (b.get("brand"), b.get("product_name"),
                                  b.get("size"))
                if part
            )
            ctk.CTkLabel(row, text=display,
                         width=180, anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3, pady=6)

            ctk.CTkLabel(row, text=b.get("batch_no") or "-",
                         width=130, anchor="w",
                         font=font(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

            ctk.CTkLabel(row, text=str(b.get("quantity") or 0),
                         width=50, anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3)

            exp_str = b.get("expiration_date") or "—"
            days_left = None
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
            except (ValueError, TypeError):
                pass

            if days_left is None:
                exp_text, exp_color = exp_str, FG_MUTED
            elif days_left < 0:
                exp_text, exp_color = f"{exp_str} (expired)", DANGER
            elif days_left <= 7:
                exp_text, exp_color = f"{exp_str} ({days_left}d)", DANGER
            elif days_left <= 30:
                exp_text, exp_color = f"{exp_str} ({days_left}d)", "#D97706"
            else:
                exp_text, exp_color = exp_str, FG_SECONDARY

            ctk.CTkLabel(row, text=exp_text,
                         width=130, anchor="w",
                         font=font_bold(11),
                         text_color=exp_color).pack(side="left", padx=3)

        self._update_pager(self.expiring_pager,
                           self.expiring_page, self.expiring_total_pages)

    # ─────────────────────────────────────────────
    # LOW STOCK
    # ─────────────────────────────────────────────

    def _render_low_stock(self):
        for w in self.lowstock_frame.winfo_children():
            w.destroy()

        try:
            rows = list(DashboardController.low_stock_products(limit=500))
        except Exception as e:
            print(f"[Dashboard] low_stock_products failed: {e}")
            rows = []

        total = len(rows)
        self.lowstock_total_pages = max(
            1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        )
        if self.lowstock_page > self.lowstock_total_pages:
            self.lowstock_page = self.lowstock_total_pages

        start = (self.lowstock_page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_rows = rows[start:end]

        if not page_rows:
            ctk.CTkLabel(self.lowstock_frame,
                         text="All products are well-stocked.",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=30)
            self._update_pager(self.lowstock_pager, 1, 1)
            return

        header = ctk.CTkFrame(self.lowstock_frame, fg_color="transparent")
        header.pack(fill="x", pady=(4, 8))

        for text, width in [
            ("Product",    180),
            ("Category",    90),
            ("Stock",       55),
            ("Min",         45),
        ]:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=4)

        for i, p in enumerate(page_rows):
            bg = BG_ROW_ALT if i % 2 else BG_CARD

            row = ctk.CTkFrame(self.lowstock_frame, fg_color=bg, corner_radius=6)
            row.pack(fill="x", pady=2)

            display = " ".join(
                part for part in (p.get("brand"), p["name"], p.get("size"))
                if part
            )

            ctk.CTkLabel(row, text=display,
                         width=180, anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=4, pady=6)

            ctk.CTkLabel(row, text=p["category_name"] or "-",
                         width=90, anchor="w",
                         font=font(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=4)

            stock = p["stock_qty"]
            if stock <= 0:
                stock_text, stock_color = "Out", DANGER
            else:
                stock_text, stock_color = f"{stock}", "#D97706"

            ctk.CTkLabel(row, text=stock_text,
                         width=55, anchor="w",
                         font=font_bold(11),
                         text_color=stock_color).pack(side="left", padx=4)

            ctk.CTkLabel(row, text=str(p["low_stock_level"] or 0),
                         width=45, anchor="w",
                         font=font(11),
                         text_color=FG_MUTED).pack(side="left", padx=4)

        self._update_pager(self.lowstock_pager,
                           self.lowstock_page, self.lowstock_total_pages)

    # ─────────────────────────────────────────────
    # PAGER STATE
    # ─────────────────────────────────────────────

    def _update_pager(self, pager, current, total):
        pager["label"].configure(text=f"Page {current} of {total}")

        if current <= 1:
            pager["prev"].configure(state="disabled",
                                    fg_color=BG_INPUT,
                                    text_color=FG_MUTED)
        else:
            pager["prev"].configure(state="normal",
                                    fg_color=NEUTRAL,
                                    text_color=NEUTRAL_TEXT)

        if current >= total:
            pager["next"].configure(state="disabled",
                                    fg_color=BG_INPUT,
                                    text_color=FG_MUTED)
        else:
            pager["next"].configure(state="normal",
                                    fg_color=NEUTRAL,
                                    text_color=NEUTRAL_TEXT)


# ─────────────────────────────────────────────
# TODAY'S SALES POPUP (transaction list, reusable, non-modal)
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# TODAY'S SALES POPUP (transaction list, reusable, non-modal)
# ─────────────────────────────────────────────

class TodaySalesDialog(ctk.CTkToplevel):
    """
    Non-modal popup listing today's transactions.
    Each row has a View button that opens the shared TransactionDetailDialog.

    Reusable: closing hides it (withdraw). Calling load() rebuilds the
    list in place. The instance survives across KPI clicks.

    Windows z-order: uses _pop_to_front from views.transaction_dialogs
    to force itself in front of the main window after being shown.
    """

    def __init__(self, parent, stats):
        super().__init__(parent)
        self.parent = parent

        self.title("Today's Sales")
        self.geometry("900x560")
        self.minsize(820, 500)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)

        # Override close so we hide instead of destroy
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Container that gets rebuilt on each load()
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

        self._stats = {}
        self.load(stats=stats)

    # ─────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────

    def load(self, stats):
        """Rebuild the popup with fresh data."""
        self._stats = stats or {}
        self._rebuild()

        try:
            self.update_idletasks()
            center_on_parent(self, self.parent)
        except Exception:
            pass

        # ⚡ Force to front
        try:
            from views.transaction_dialogs import _pop_to_front
            _pop_to_front(self)
        except Exception:
            try:
                self.lift()
                self.focus_force()
            except Exception:
                pass

    def _on_close(self):
        # ⚡ Release any stale grab, then hide — reuse on next KPI click
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.withdraw()
        except Exception:
            pass

    # ─────────────────────────────────────────────
    # REBUILD
    # ─────────────────────────────────────────────

    def _rebuild(self):
        for w in self._container.winfo_children():
            w.destroy()

        # ---- Title ----
        header = ctk.CTkFrame(self._container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 4))

        ctk.CTkLabel(header,
                     text="Today's Sales",
                     font=font_bold(17),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(fill="x")

        ctk.CTkLabel(header,
                     text=datetime.now().strftime("%A, %B %d, %Y"),
                     font=font(11),
                     text_color=FG_SECONDARY,
                     anchor="w").pack(fill="x", pady=(2, 0))

        # ---- Big total ----
        total = self._stats.get("total_sales_today", 0) or 0

        total_box = ctk.CTkFrame(self._container, fg_color="#EAF0FF",
                                 corner_radius=10)
        total_box.pack(fill="x", padx=20, pady=(12, 10))

        ctk.CTkLabel(total_box,
                     text="TOTAL SALES",
                     font=font_bold(10),
                     text_color=FG_SECONDARY,
                     anchor="w").pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(total_box,
                     text=f"₱{total:,.2f}",
                     font=font_bold(26),
                     text_color=ACCENT,
                     anchor="w").pack(fill="x", padx=16, pady=(0, 12))

        # ---- Transaction list ----
        today_db = datetime.now().strftime("%Y-%m-%d")
        try:
            transactions = TransactionController.list(
                date_from=today_db,
                date_to=today_db,
            )
        except Exception as e:
            print(f"[TodaySales] fetch failed: {e}")
            transactions = []

        list_card = ctk.CTkFrame(self._container, fg_color=BG_CARD,
                                 corner_radius=12,
                                 border_width=1,
                                 border_color=BORDER)
        list_card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # ---- Column header ----
        header_row = ctk.CTkFrame(list_card, fg_color="transparent")
        header_row.pack(fill="x", padx=14, pady=(12, 6))
        cols = [
            ("Txn #",        70),
            ("Date & Time",  150),
            ("Cashier",      140),
            ("Payment",      90),
            ("Total",       110),
            ("",             80),
        ]
        for text, width in cols:
            ctk.CTkLabel(header_row, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        ctk.CTkFrame(list_card, height=1, fg_color=BORDER).pack(
            fill="x", padx=14)

        # ---- Rows (scrollable) ----
        if not transactions:
            ctk.CTkLabel(list_card,
                         text="No transactions today.",
                         font=font(12),
                         text_color=FG_MUTED).pack(pady=30)
        else:
            body = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=8, pady=(4, 10))

            for i, t in enumerate(transactions):
                self._render_row(body, t, i)

        # ---- Close button ----
        ctk.CTkButton(self._container, text="Close",
                      height=38, corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._on_close
                      ).pack(side="bottom", fill="x", padx=20, pady=(0, 16))

    def _render_row(self, parent, t, index):
        bg = BG_ROW_ALT if index % 2 else "transparent"
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=6)
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(row, text=f"#{t['transaction_id']}",
                     width=70, anchor="w",
                     font=font_bold(11),
                     text_color=ACCENT).pack(side="left", padx=3, pady=8)

        ctk.CTkLabel(row, text=t["created_at"] or "-",
                     width=150, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        cashier = t["full_name"] or t["username"] or "-"
        ctk.CTkLabel(row, text=cashier,
                     width=140, anchor="w",
                     font=font(11),
                     text_color=FG_PRIMARY).pack(side="left", padx=3)

        pay = t["payment_method"] or "-"
        pay_color = SUCCESS if pay == "Cash" else (
            ACCENT if pay == "GCash" else FG_SECONDARY
        )
        ctk.CTkLabel(row, text=pay,
                     width=90, anchor="w",
                     font=font_bold(11),
                     text_color=pay_color).pack(side="left", padx=3)

        ctk.CTkLabel(row, text=f"₱{t['total']:.2f}",
                     width=110, anchor="w",
                     font=font_bold(12),
                     text_color=ACCENT).pack(side="left", padx=3)

        ctk.CTkButton(row, text="View", width=60, height=28,
                      corner_radius=6,
                      font=font_bold(11),
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda txn=t: self._view_transaction(txn)
                      ).pack(side="right", padx=4)

    def _view_transaction(self, txn):
        dlg = TransactionDetailDialog.get_shared(self.parent)
        dlg.load_transaction(txn)
        dlg.deiconify()