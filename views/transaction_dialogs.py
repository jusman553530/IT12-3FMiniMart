# ─────────────────────────────────────────────
# SHARED TRANSACTION DIALOGS
# ─────────────────────────────────────────────
#
# TransactionDetailDialog is a reusable, singleton-style popup:
#   - only one instance exists at a time across the whole app
#   - close hides it (withdraw) instead of destroying it
#   - load_transaction(txn) swaps the content in place
#
# Windows z-order note: CTkToplevel windows opened after the main window
# has focus will sometimes render *behind* it. The _pop_to_front helper
# below forces them to the foreground using the -topmost attribute for a
# brief moment, then releases it so the window behaves normally.
#
# Usage:
#   dlg = TransactionDetailDialog.get_shared(parent)
#   dlg.load_transaction(txn)
#   dlg.deiconify()

import customtkinter as ctk
from controllers.transaction_controller import TransactionController
from utils import center_on_parent
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_ROW_ALT, BORDER,
    FG_PRIMARY, FG_SECONDARY,
    ACCENT,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


# ─────────────────────────────────────────────
# ⚡ WINDOW Z-ORDER HELPERS
# ─────────────────────────────────────────────

def _pop_to_front(win):
    """
    Force a Toplevel window to appear in front of the main window on
    Windows. The order matters:
      1. deiconify      — ensure it's mapped
      2. lift           — top of z-order (WM may ignore)
      3. -topmost True  — force the WM to honor it
      4. after(300) drop -topmost so it doesn't stay pinned
      5. focus_force    — take focus
      6. after(80) second lift, in case Windows re-ordered on first show
    """
    try:
        win.deiconify()
    except Exception:
        pass
    try:
        win.lift()
    except Exception:
        pass
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass
    try:
        win.after(300, lambda w=win: _drop_topmost(w))
    except Exception:
        pass
    try:
        win.focus_force()
    except Exception:
        pass
    try:
        win.after(80, lambda w=win: _lift_again(w))
    except Exception:
        pass


def _lift_again(win):
    try:
        if win.winfo_exists():
            win.lift()
            win.focus_force()
    except Exception:
        pass


def _drop_topmost(win):
    try:
        if win.winfo_exists():
            win.attributes("-topmost", False)
    except Exception:
        pass


# ─────────────────────────────────────────────
# TRANSACTION DETAIL DIALOG
# ─────────────────────────────────────────────

class TransactionDetailDialog(ctk.CTkToplevel):

    # ⚡ Class-level singleton: one instance for the whole app
    _shared_instance = None

    @classmethod
    def get_shared(cls, parent):
        """Return the shared dialog, creating it if needed."""
        if cls._shared_instance is None or \
           not cls._shared_instance.winfo_exists():
            cls._shared_instance = cls(parent)
        return cls._shared_instance

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title("Transaction")
        self.geometry("580x520")
        self.minsize(560, 480)
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        # Override close button so it hides, not destroys
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Container rebuilt on each load_transaction call
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

        self._current_txn_id = None

    # ─────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────

    def load_transaction(self, txn):
        """Show the given transaction. Rebuilds content in place."""
        self._current_txn_id = txn["transaction_id"]
        self.title(f"Transaction #{txn['transaction_id']}")
        self._rebuild(txn)

        try:
            self.update_idletasks()
            center_on_parent(self, self.parent)
        except Exception:
            pass

        # ⚡ Force to front (fixes the alt+tab-hiding problem)
        _pop_to_front(self)

    def _on_close(self):
        # ⚡ Release any stale grab before hiding, just in case.
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

    def _rebuild(self, txn):
        for w in self._container.winfo_children():
            w.destroy()

        t = txn

        ctk.CTkLabel(self._container,
                     text=f"Transaction #{t['transaction_id']}",
                     font=font_bold(18),
                     text_color=FG_PRIMARY).pack(pady=(18, 4))

        ctk.CTkLabel(self._container, text=t["created_at"],
                     font=font(11),
                     text_color=FG_SECONDARY).pack(pady=(0, 14))

        info = ctk.CTkFrame(self._container, fg_color=BG_CARD,
                            corner_radius=12,
                            border_width=1,
                            border_color=BORDER)
        info.pack(fill="x", padx=20, pady=(0, 10))

        rows = [
            ("Cashier",     t["full_name"] or t["username"]),
            ("Payment",     t["payment_method"]),
        ]
        if t["payment_method"] == "GCash":
            ref = t.get("gcash_reference")
            if ref:
                rows.append(("GCash Reference", ref))
        rows += [
            ("Amount Paid", f"₱{t['amount_paid']:.2f}"),
            ("Change",      f"₱{t['change_due']:.2f}"),
            ("Total",       f"₱{t['total']:.2f}"),
        ]
        for i, (label, value) in enumerate(rows):
            if i > 0:
                ctk.CTkFrame(info, height=1, fg_color=BORDER).pack(
                    fill="x", padx=14)

            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=8)

            ctk.CTkLabel(row, text=label,
                         font=font_bold(11),
                         text_color=FG_SECONDARY,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="e",
                         font=font_bold(12),
                         text_color=FG_PRIMARY).pack(side="right")

        ctk.CTkLabel(self._container, text="Items Purchased",
                     font=font_bold(13),
                     text_color=FG_PRIMARY).pack(pady=(10, 4))

        items_card = ctk.CTkFrame(self._container, fg_color=BG_CARD,
                                  corner_radius=12,
                                  border_width=1,
                                  border_color=BORDER)
        items_card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        lines = ctk.CTkScrollableFrame(items_card, fg_color="transparent")
        lines.pack(fill="both", expand=True, padx=8, pady=8)

        header = ctk.CTkFrame(lines, fg_color="transparent")
        header.pack(fill="x", pady=(2, 6))
        for text, width in [("Item", 220), ("Qty", 60),
                            ("Price", 100), ("Subtotal", 110)]:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        items = TransactionController.items(t["transaction_id"])
        for i, it in enumerate(items):
            bg = BG_ROW_ALT if i % 2 else "transparent"
            row = ctk.CTkFrame(lines, fg_color=bg, corner_radius=6)
            row.pack(fill="x", pady=1)

            ctk.CTkLabel(row, text=it["product_name"],
                         width=220, anchor="w",
                         font=font(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3, pady=6)
            ctk.CTkLabel(row, text=f"×{it['quantity']}",
                         width=60, anchor="w",
                         font=font(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)
            ctk.CTkLabel(row, text=f"₱{it['price']:.2f}",
                         width=100, anchor="w",
                         font=font(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3)
            ctk.CTkLabel(row, text=f"₱{it['subtotal']:.2f}",
                         width=110, anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=3)

        ctk.CTkButton(self._container, text="Close", width=140, height=38,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._on_close).pack(pady=(6, 16))