# ─────────────────────────────────────────────
# RECEIVE PURCHASE ORDER DIALOG
# ─────────────────────────────────────────────
#
# Columns:
#   ✓               — checkbox
#   Code            — product code
#   Name            — product name | size
#   Ordered         — ordered qty + unit (informational)
#   Received        — editable: boxes/packs arrived (digits only)
#   Cost / Unit     — editable: cost per box/pack (money)
#   Expiration Date — editable: MM/DD/YYYY (auto-formatted)
#   Total Pieces    — editable: pieces → inventory (digits only)
#
# Bottom:
#   Total Amount of Purchase Order — auto = Σ (Cost/Unit × Received)
#
# IMPORTANT — modal contract:
#   Caller must do:
#       dialog = ReceiveConfirmDialog(parent, purchase, items)
#       dialog.wait_window()
#       if dialog.confirmed: ...

import customtkinter as ctk
from tkinter import messagebox

from utils import (
    prepare_dialog_screen,
    ui_date_to_db,
    is_valid_ui_date,
)
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_ROW_ALT, BG_INPUT, BORDER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    BRAND_GREEN, ACCENT,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


# ─────────────────────────────────────────────
# ⚡ INPUT VALIDATORS
# ─────────────────────────────────────────────

def _validate_int_input(proposed: str) -> bool:
    """Digits only. Empty string allowed (user clearing the field)."""
    if proposed == "":
        return True
    return proposed.isdigit()


def _validate_money_input(proposed: str) -> bool:
    """Digits and at most one decimal point with up to 2 decimals."""
    if proposed == "":
        return True
    if not all(ch.isdigit() or ch == "." for ch in proposed):
        return False
    if proposed.count(".") > 1:
        return False
    if "." in proposed:
        _, _, decimals = proposed.partition(".")
        if len(decimals) > 2:
            return False
    return True


def _validate_date_input(proposed: str) -> bool:
    """Allow digits and '/' only, max length 10 (MM/DD/YYYY)."""
    if proposed == "":
        return True
    if len(proposed) > 10:
        return False
    return all(ch.isdigit() or ch == "/" for ch in proposed)


def _autofill_date_slashes(raw: str) -> str:
    """Insert '/' automatically after MM and DD. Strips existing slashes
    first so backspacing still works."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    digits = digits[:8]  # max MMDDYYYY

    if len(digits) <= 2:
        return digits
    if len(digits) <= 4:
        return f"{digits[:2]}/{digits[2:]}"
    return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"


class ReceiveConfirmDialog(ctk.CTkToplevel):

    def __init__(self, parent, purchase, items):
        super().__init__(parent)
        self.parent = parent
        self.purchase = purchase
        self.items = items
        self.confirmed = False

        self._check_vars = {}          # product_id → BooleanVar
        self._received_entries = {}    # product_id → Entry (boxes/packs)
        self._cost_entries = {}        # product_id → Entry (cost per unit)
        self._expiry_entries = {}      # product_id → Entry (MM/DD/YYYY)
        self._pieces_entries = {}      # product_id → Entry (pieces)

        self.received_quantities = {}  # { product_id: pieces }
        self.line_costs = {}           # { product_id: cost_per_unit }
        self.expiration_dates = {}     # { product_id: "YYYY-MM-DD" or None }
        self.total_amount = 0.0

        self._total_overridden = False

        self.title(f"Receive PO #{purchase['purchase_id']}")
        self.geometry("1220x740")
        self.minsize(1120, 640)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)

        self._build()
        prepare_dialog_screen(self, self.parent)
        self.after(10, self._finalize_modal)

    def _finalize_modal(self):
        if not self.winfo_exists():
            return
        try:
            self.transient(self.parent)
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ─────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────

    def _build(self):
        p = self.purchase

        ctk.CTkLabel(self,
                     text=f"Receive PO #{p['purchase_id']}",
                     font=font_bold(18),
                     text_color=FG_PRIMARY).pack(pady=(18, 4))

        ctk.CTkLabel(self,
                     text=p["supplier_name"] or "Unknown Supplier",
                     font=font(12),
                     text_color=FG_SECONDARY).pack(pady=(0, 4))

        ctk.CTkLabel(self,
                     text="Check each item that arrived. Total Pieces is what "
                          "gets added to inventory. Expiration Date is "
                          "MM/DD/YYYY (optional). Total Amount auto-fills "
                          "from Cost × Received, but you can edit it.",
                     font=font(11),
                     text_color=FG_MUTED,
                     wraplength=1120,
                     justify="center").pack(pady=(0, 14))

        # ═════════════════════════════════════════
        # BUTTONS
        # ═════════════════════════════════════════

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=20, pady=(8, 16))

        ctk.CTkButton(btn_row, text="Cancel",
                      width=140, height=40,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._cancel).pack(side="left")

        self.toggle_all_btn = ctk.CTkButton(
            btn_row, text="Deselect All",
            width=130, height=40,
            corner_radius=8,
            font=font_bold(11),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
            text_color=NEUTRAL_TEXT,
            command=self._toggle_all,
        )
        self.toggle_all_btn.pack(side="left", padx=(8, 0))

        ctk.CTkButton(btn_row, text="Confirm Receive",
                      height=40,
                      corner_radius=8,
                      font=font_bold(13),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=self._confirm).pack(side="right", fill="x",
                                                  expand=True, padx=(8, 0))

        # ═════════════════════════════════════════
        # INFO CARD
        # ═════════════════════════════════════════

        info = ctk.CTkFrame(self, fg_color=BG_CARD,
                            corner_radius=12,
                            border_width=1,
                            border_color=BORDER)
        info.pack(fill="x", padx=20, pady=(0, 10))

        info_rows = [
            ("Ordered By",    p["full_name"] or p["username"] or "-"),
            ("Date Ordered",  p["created_at"] or "-"),
        ]
        for i, (label, value) in enumerate(info_rows):
            if i > 0:
                ctk.CTkFrame(info, height=1, fg_color=BORDER).pack(
                    fill="x", padx=14)

            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=7)

            ctk.CTkLabel(row, text=label,
                         width=120, anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left")

            ctk.CTkLabel(row, text=str(value), anchor="w",
                         font=font(12),
                         text_color=FG_PRIMARY).pack(side="left")

        # ═════════════════════════════════════════
        # ITEMS CARD
        # ═════════════════════════════════════════

        items_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                  corner_radius=12,
                                  border_width=1,
                                  border_color=BORDER)
        items_card.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self.summary_label = ctk.CTkLabel(
            items_card,
            text="",
            font=font_bold(13),
            text_color=FG_PRIMARY,
        )
        self.summary_label.pack(pady=(12, 4))

        lines = ctk.CTkScrollableFrame(items_card, fg_color="transparent")
        lines.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ---- Column header ----
        header = ctk.CTkFrame(lines, fg_color="transparent")
        header.pack(fill="x", pady=(4, 8))
        header_cols = [
            ("✓",                36),
            ("Code",             80),
            ("Name",            200),
            ("Ordered",         105),
            ("Received",         90),
            ("Cost / Unit",     100),
            ("Expiration Date ", 150),
            ("Total Pieces",    90),
        ]
        for text, width in header_cols:
            ctk.CTkLabel(header, text=text, width=width,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=3)

        # ---- Rows ----
        if not self.items:
            ctk.CTkLabel(lines,
                         text="No items on this purchase order.",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=20)
        else:
            for i, it in enumerate(self.items, start=1):
                self._render_item_row(lines, it, i)

        # ═════════════════════════════════════════
        # TOTAL AMOUNT CARD
        # ═════════════════════════════════════════

        total_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                  corner_radius=12,
                                  border_width=1,
                                  border_color=BORDER)
        total_card.pack(fill="x", padx=20, pady=(0, 12))

        total_row = ctk.CTkFrame(total_card, fg_color="transparent")
        total_row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(total_row,
                     text="Total Amount of Purchase Order (₱)",
                     font=font_bold(12),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(side="left")

        ctk.CTkButton(total_row, text="Reset to Auto",
                      width=110, height=30,
                      corner_radius=6,
                      font=font_bold(10),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._reset_total_to_auto).pack(
                          side="right", padx=(8, 0))

        # ⚡ Total Amount — money validation
        total_vcmd = (self.register(_validate_money_input), "%P")
        self.total_entry = ctk.CTkEntry(
            total_row,
            width=180, height=36,
            corner_radius=8,
            font=font_bold(14),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            justify="right",
            validate="key", validatecommand=total_vcmd,
        )
        self.total_entry.pack(side="right")
        self.total_entry.bind("<KeyRelease>", self._on_total_typed)

        self._recompute_total()
        self._refresh_summary()

    def _render_item_row(self, parent, item, index):
        bg = BG_ROW_ALT if index % 2 == 0 else BG_CARD
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=6)
        row.pack(fill="x", pady=2)

        qty    = item["quantity"] or 0
        unit   = item["unit"] if "unit" in item.keys() and item["unit"] else "pc"
        pieces = item["pieces_per_unit"] if "pieces_per_unit" in item.keys() else 1
        pieces = pieces or 1

        # ---- Checkbox ----
        var = ctk.BooleanVar(value=True)
        self._check_vars[item["product_id"]] = var

        ctk.CTkCheckBox(
            row,
            text="",
            variable=var,
            width=28,
            checkbox_width=22,
            checkbox_height=22,
            corner_radius=4,
            fg_color=BRAND_GREEN,
            hover_color="#1E9040",
            border_color=BORDER,
            command=self._refresh_summary,
        ).pack(side="left", padx=(8, 4), pady=6)

        # ---- Code ----
        ctk.CTkLabel(row, text=item["product_code"] or "-",
                     width=80, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        # ---- Name (with size joined) ----
        name_parts = [item["product_name"]]
        size = item["product_size"] if "product_size" in item.keys() else None
        if size:
            name_parts.append(size)
        display_name = " | ".join(p for p in name_parts if p)

        ctk.CTkLabel(row, text=display_name,
                     width=200, anchor="w",
                     font=font_bold(11),
                     text_color=FG_PRIMARY).pack(side="left", padx=3)

        # ---- Ordered ----
        ordered_text = f"{qty} {unit}"
        if pieces > 1:
            ordered_text += f" ({qty * pieces} pc)"

        ctk.CTkLabel(row, text=ordered_text,
                     width=105, anchor="w",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(side="left", padx=3)

        # ---- Received (editable, boxes/packs) — digits only ----
        recv_vcmd = (self.register(_validate_int_input), "%P")
        recv_e = ctk.CTkEntry(
            row,
            width=80, height=30,
            corner_radius=6,
            font=font(12),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            justify="center",
            placeholder_text="0",
            validate="key", validatecommand=recv_vcmd,
        )
        recv_e.pack(side="left", padx=3)
        recv_e.insert(0, str(qty))
        recv_e.bind("<KeyRelease>",
                    lambda e, pid=item["product_id"]: self._recompute_total())
        self._received_entries[item["product_id"]] = recv_e

        # ---- Cost / Unit (editable) — money ----
        cost_vcmd = (self.register(_validate_money_input), "%P")
        cost_e = ctk.CTkEntry(
            row,
            width=90, height=30,
            corner_radius=6,
            font=font(12),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            justify="center",
            placeholder_text="0.00",
            validate="key", validatecommand=cost_vcmd,
        )
        cost_e.pack(side="left", padx=3)
        cost_e.bind("<KeyRelease>",
                    lambda e, pid=item["product_id"]: self._recompute_total())
        self._cost_entries[item["product_id"]] = cost_e

        # ---- Expiration Date (auto-format MM/DD/YYYY) ----
        # NOTE: no validate="key" here — CTk's placeholder logic conflicts
        # with Tk's validation. The auto-slash formatter enforces the shape
        # as the user types, and _confirm() validates the final date.
        expiry_e = ctk.CTkEntry(
            row,
            width=140, height=30,
            corner_radius=6,
            font=font(12),
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            justify="center",
            placeholder_text="MM/DD/YYYY",
        )
        expiry_e.pack(side="left", padx=3)

        # If the PO line already carries an expiration date, pre-fill it
        existing = None
        if "expiration_date" in item.keys():
            existing = item["expiration_date"]
        if existing:
            try:
                y, m, d = existing.split("-")
                expiry_e.insert(0, f"{m}/{d}/{y}")
            except Exception:
                expiry_e.insert(0, existing)

        # Auto-insert "/" separators as the user types
        expiry_e.bind(
            "<KeyRelease>",
            lambda e, entry=expiry_e: self._reformat_expiry(entry)
        )

        self._expiry_entries[item["product_id"]] = expiry_e

        # ---- Total Pieces (editable) — digits only ----
        pieces_vcmd = (self.register(_validate_int_input), "%P")
        default_pieces = qty * pieces
        pieces_e = ctk.CTkEntry(
            row,
            width=95, height=30,
            corner_radius=6,
            font=font_bold(12),
            fg_color=BG_INPUT,
            border_color=ACCENT,
            border_width=2,
            justify="center",
            validate="key", validatecommand=pieces_vcmd,
        )
        pieces_e.pack(side="left", padx=3)
        pieces_e.insert(0, str(default_pieces))
        self._pieces_entries[item["product_id"]] = pieces_e

    # ─────────────────────────────────────────────
    # ⚡ EXPIRY AUTO-FORMAT HELPER
    # ─────────────────────────────────────────────

    def _reformat_expiry(self, entry):
        """Insert '/' separators as the user types. Keeps cursor at end."""
        current = entry.get()
        formatted = _autofill_date_slashes(current)
        if formatted != current:
            entry.delete(0, "end")
            entry.insert(0, formatted)
            entry.icursor("end")

    # ─────────────────────────────────────────────
    # TOTAL MATH
    # ─────────────────────────────────────────────

    def _recompute_total(self):
        if self._total_overridden:
            return

        total = 0.0
        for product_id, var in self._check_vars.items():
            if not var.get():
                continue

            cost_e = self._cost_entries.get(product_id)
            recv_e = self._received_entries.get(product_id)

            try:
                cost_val = float((cost_e.get() if cost_e else "0").strip() or 0)
            except (ValueError, AttributeError):
                cost_val = 0.0
            try:
                recv_val = float((recv_e.get() if recv_e else "0").strip() or 0)
            except (ValueError, AttributeError):
                recv_val = 0.0

            total += cost_val * recv_val

        if not self.total_entry.winfo_exists():
            return
        self.total_entry.delete(0, "end")
        self.total_entry.insert(0, f"{total:.2f}")

    def _on_total_typed(self, *args):
        self._total_overridden = True

    def _reset_total_to_auto(self):
        self._total_overridden = False
        self._recompute_total()

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _refresh_summary(self):
        checked = sum(1 for v in self._check_vars.values() if v.get())
        total   = len(self._check_vars)

        self.summary_label.configure(
            text=f"Items to Receive: {checked} of {total} selected"
        )

        if checked == total and total > 0:
            self.toggle_all_btn.configure(text="Deselect All")
        else:
            self.toggle_all_btn.configure(text="Select All")

        self._recompute_total()

    def _toggle_all(self):
        checked = sum(1 for v in self._check_vars.values() if v.get())
        total   = len(self._check_vars)
        should_check = not (checked == total and total > 0)

        for v in self._check_vars.values():
            v.set(should_check)

        self._refresh_summary()

    # ─────────────────────────────────────────────
    # CONFIRM / CANCEL
    # ─────────────────────────────────────────────

    def _confirm(self):
        # ---- 1. PO total ----
        raw_total = self.total_entry.get().strip()
        try:
            total_amount = float(raw_total)
            if total_amount < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid Total Amount",
                "Please enter a valid number for the Total Amount "
                "of the Purchase Order.",
                parent=self,
            )
            self.total_entry.focus_set()
            return

        # ---- 2. Gather + validate ----
        received = {}
        costs = {}
        expiries = {}

        for product_id, var in self._check_vars.items():
            if not var.get():
                continue

            # ---- Total Pieces ----
            pieces_e = self._pieces_entries.get(product_id)
            if pieces_e is None:
                continue

            raw_pieces = pieces_e.get().strip()
            try:
                pieces_val = int(raw_pieces)
                if pieces_val < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid Total Pieces",
                    "Please enter a whole number for Total Pieces.",
                    parent=self,
                )
                return

            if pieces_val == 0:
                continue

            # ---- Cost / Unit ----
            cost_e = self._cost_entries.get(product_id)
            raw_cost = (cost_e.get() if cost_e else "0").strip() or "0"
            try:
                cost_val = float(raw_cost)
                if cost_val < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid Cost",
                    "Please enter a valid number for Cost / Unit.",
                    parent=self,
                )
                return

            # ---- Expiration Date (optional, MM/DD/YYYY) ----
            expiry_e = self._expiry_entries.get(product_id)
            raw_expiry = (expiry_e.get() if expiry_e else "").strip()
            db_expiry = None

            if raw_expiry:
                if not is_valid_ui_date(raw_expiry):
                    messagebox.showerror(
                        "Invalid Expiration Date",
                        "Please use MM/DD/YYYY for the expiration date, "
                        "or leave it blank.",
                        parent=self,
                    )
                    return
                db_expiry = ui_date_to_db(raw_expiry)

            received[product_id] = pieces_val
            costs[product_id] = cost_val
            expiries[product_id] = db_expiry

        if not received:
            messagebox.showwarning(
                "Nothing to Receive",
                "Please check at least one item and enter a Total Pieces "
                "value greater than 0, or click Cancel.",
                parent=self,
            )
            return

        self.received_quantities = received
        self.line_costs = costs
        self.expiration_dates = expiries
        self.total_amount = total_amount
        self.confirmed = True
        self.destroy()

    def _cancel(self):
        self.confirmed = False
        self.received_quantities = {}
        self.line_costs = {}
        self.expiration_dates = {}
        self.total_amount = 0.0
        self.destroy()
        