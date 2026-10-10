# ─────────────────────────────────────────────
# NEW PURCHASE ORDER DIALOG
# ─────────────────────────────────────────────
#
# Extracted from purchase_view.py.
#
# Usage:
#     PurchaseOrderDialog(parent, user, on_save=callback)

import customtkinter as ctk
from tkinter import messagebox

from controllers.purchase_controller import PurchaseController
from controllers.supplier_controller import SupplierController
from controllers.inventory_controller import InventoryController
from utils import prepare_dialog_screen
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BG_INPUT, BG_ROW_ALT, BORDER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    BRAND_GREEN,
    ACCENT,
    SUCCESS, DANGER,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)


# ─────────────────────────────────────────────
# UNIT OPTIONS
# ─────────────────────────────────────────────

UNIT_OPTIONS = ["pc", "pack", "box", "case", "sack", "kg", "L"]


class PurchaseOrderDialog(ctk.CTkToplevel):

    def __init__(self, parent, user, on_save):
        super().__init__(parent)
        self.parent = parent
        self.user = user
        self.on_save = on_save
        self.title("New Purchase Order")

        self.geometry("920x560")
        self.minsize(820, 520)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)

        self.suppliers = SupplierController.list_suppliers()
        self.cart = []
        self._supplier_products = []

        self._build()
        prepare_dialog_screen(self, self.parent)

    # ─────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────

    def _build(self):
        # ═════════════════════════════════════════
        # BUTTONS FIRST — pinned to bottom
        # ═════════════════════════════════════════

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=20, pady=(4, 14))

        ctk.CTkButton(btn_row, text="Clear",
                      width=100, height=38,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._clear).pack(side="left")

        ctk.CTkButton(btn_row, text="Place Order",
                      height=38,
                      corner_radius=8,
                      font=font_bold(13),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=self._save).pack(side="right", fill="x",
                                               expand=True, padx=(8, 0))

        # ═════════════════════════════════════════
        # HEADER
        # ═════════════════════════════════════════

        ctk.CTkLabel(self, text="New Purchase Order",
                     font=font_bold(18),
                     text_color=FG_PRIMARY).pack(pady=(14, 2))

        ctk.CTkLabel(self, text="Select a supplier, then add products to order",
                     font=font(11),
                     text_color=FG_SECONDARY).pack(pady=(0, 8))

        # ═════════════════════════════════════════
        # SUPPLIER
        # ═════════════════════════════════════════

        sup_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                corner_radius=10,
                                border_width=1,
                                border_color=BORDER)
        sup_card.pack(fill="x", padx=20, pady=(0, 8))

        sup_row = ctk.CTkFrame(sup_card, fg_color="transparent")
        sup_row.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(sup_row, text="SUPPLIER",
                     font=font_bold(10),
                     text_color=FG_SECONDARY).pack(side="left", padx=(0, 10))

        self.supplier_names = [s["name"] for s in self.suppliers] or ["(No suppliers)"]
        self.supplier_var = ctk.StringVar(value=self.supplier_names[0])
        self.supplier_menu = ctk.CTkOptionMenu(
            sup_row, values=self.supplier_names,
            variable=self.supplier_var,
            width=280, height=34,
            corner_radius=8,
            font=font(12),
            fg_color=BG_INPUT,
            button_color=BG_INPUT,
            button_hover_color=NEUTRAL,
            text_color=FG_PRIMARY,
            command=self._on_supplier_change,
        )
        self.supplier_menu.pack(side="left", padx=(0, 10))

        ctk.CTkButton(sup_row, text="Refresh", width=100, height=34,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self._load_products_for_supplier
                      ).pack(side="left")

        # ═════════════════════════════════════════
        # BODY (two columns)
        # ═════════════════════════════════════════

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        # ---- LEFT: products of supplier ----
        left = ctk.CTkFrame(body, fg_color=BG_CARD,
                            corner_radius=10,
                            border_width=1,
                            border_color=BORDER)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctk.CTkLabel(left, text="Products of Supplier",
                     font=font_bold(12),
                     text_color=FG_PRIMARY).pack(pady=(10, 2))

        ctk.CTkLabel(left,
                     text="Click a product to add it to the order",
                     font=font(10),
                     text_color=FG_MUTED).pack(pady=(0, 4))

        prod_header = ctk.CTkFrame(left, fg_color="transparent")
        prod_header.pack(fill="x", padx=8, pady=(0, 4))
        for text, width in [("Name", 140), ("Size", 60), ("Unit", 45),
                            ("Category", 90), ("Stock", 55)]:
            ctk.CTkLabel(prod_header, text=text, width=width,
                         anchor="w", font=font_bold(10),
                         text_color=FG_SECONDARY).pack(side="left", padx=2)

        self.products_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.products_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ---- RIGHT: order lines ----
        right = ctk.CTkFrame(body, fg_color=BG_CARD,
                             corner_radius=10,
                             border_width=1,
                             border_color=BORDER)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(right, text="Order Lines",
                     font=font_bold(12),
                     text_color=FG_PRIMARY).pack(pady=(10, 2))

        line_header = ctk.CTkFrame(right, fg_color="transparent")
        line_header.pack(fill="x", padx=8, pady=(0, 4))

        # spacer for the ✕ column (32px wide + padx)
        spacer = ctk.CTkFrame(line_header, fg_color="transparent",
                              width=36, height=1)
        spacer.pack(side="right", padx=(0, 6))
        spacer.pack_propagate(False)

        for text, width in [("Name", 140), ("Size", 60), ("Qty", 160)]:
            ctk.CTkLabel(line_header, text=text, width=width,
                         anchor="w", font=font_bold(10),
                         text_color=FG_SECONDARY).pack(side="left", padx=2)

        self.lines_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.lines_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ═════════════════════════════════════════
        # TOTAL
        # ═════════════════════════════════════════

        total_row = ctk.CTkFrame(self, fg_color="transparent")
        total_row.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(total_row, text="TOTAL",
                     font=font_bold(10),
                     text_color=FG_SECONDARY).pack(side="left")

        self.total_label = ctk.CTkLabel(total_row, text="₱0.00",
                                        font=font_bold(18),
                                        text_color=ACCENT)
        self.total_label.pack(side="right")

        # ═════════════════════════════════════════
        # NOTES
        # ═════════════════════════════════════════

        notes_row = ctk.CTkFrame(self, fg_color="transparent")
        notes_row.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(notes_row, text="NOTES",
                     font=font_bold(10),
                     text_color=FG_SECONDARY).pack(anchor="w", pady=(0, 4))

        self.notes_e = ctk.CTkEntry(notes_row, height=34,
                                    corner_radius=8,
                                    font=font(12),
                                    fg_color=BG_INPUT,
                                    border_color=BORDER,
                                    border_width=1,
                                    placeholder_text="Optional notes for this order")
        self.notes_e.pack(fill="x")

        self._load_products_for_supplier()

    # ─────────────────────────────────────────────
    # SUPPLIER
    # ─────────────────────────────────────────────

    def _on_supplier_change(self, choice):
        self._load_products_for_supplier()

    def _get_selected_supplier_id(self):
        supplier_name = self.supplier_var.get()
        for s in self.suppliers:
            if s["name"] == supplier_name:
                return s["supplier_id"]
        return None

    # ─────────────────────────────────────────────
    # PRODUCTS
    # ─────────────────────────────────────────────

    def _load_products_for_supplier(self):
        for w in self.products_frame.winfo_children():
            w.destroy()

        supplier_id = self._get_selected_supplier_id()
        if supplier_id is None:
            ctk.CTkLabel(self.products_frame,
                         text="(no supplier selected)",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=10)
            return

        products = InventoryController.list_by_supplier(supplier_id)
        self._supplier_products = products

        if not products:
            ctk.CTkLabel(self.products_frame,
                         text="No products for this supplier.",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=10)
            return

        for p in products:
            self._render_product_row(p)

    def _render_product_row(self, p):
        stock_qty = p.get("stock_qty", 0) if hasattr(p, "get") else p["stock_qty"]
        low_level = ((p.get("low_stock_level", 0) or 0)
                     if hasattr(p, "get") else (p["low_stock_level"] or 0))

        if stock_qty <= 0:
            stock_color = DANGER
        elif stock_qty <= low_level:
            stock_color = "#D97706"
        else:
            stock_color = SUCCESS

        row = ctk.CTkFrame(self.products_frame,
                           fg_color=BG_INPUT,
                           corner_radius=6,
                           border_width=1,
                           border_color=BORDER,
                           height=38)
        row.pack(fill="x", pady=3)
        row.pack_propagate(False)

        name_label = ctk.CTkLabel(row, text=p["name"] or "-",
                                  width=140, anchor="w",
                                  font=font_bold(11),
                                  text_color=FG_PRIMARY)
        name_label.pack(side="left", padx=2)

        size_label = ctk.CTkLabel(row, text=p.get("size") or "-",
                                  width=60, anchor="w",
                                  font=font(11),
                                  text_color=FG_SECONDARY)
        size_label.pack(side="left", padx=2)

        unit_label = ctk.CTkLabel(row, text=p.get("unit") or "-",
                                  width=45, anchor="w",
                                  font=font(11),
                                  text_color=FG_SECONDARY)
        unit_label.pack(side="left", padx=2)

        cat_label = ctk.CTkLabel(row, text=p.get("category_name") or "-",
                                 width=90, anchor="w",
                                 font=font(11),
                                 text_color=FG_SECONDARY)
        cat_label.pack(side="left", padx=2)

        stock_label = ctk.CTkLabel(row, text=f"{stock_qty}",
                                   width=55, anchor="w",
                                   font=font_bold(11),
                                   text_color=stock_color)
        stock_label.pack(side="left", padx=2)

        widgets = [row, name_label, size_label, unit_label, cat_label, stock_label]
        for w in widgets:
            w.bind("<Button-1>", lambda e, prod=p: self._add_line(prod))
            w.bind("<Enter>", lambda e, r=row: r.configure(fg_color="#EAF0FF"))
            w.bind("<Leave>", lambda e, r=row: r.configure(fg_color=BG_INPUT))
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    # ─────────────────────────────────────────────
    # ADD LINE
    # ─────────────────────────────────────────────

    def _add_line(self, product):
        for line in self.cart:
            if line["product_id"] == product["product_id"]:
                messagebox.showinfo("Already added",
                                    f"{product['name']} is already in the order.")
                return

        prompt = ctk.CTkToplevel(self)
        prompt.title(f"Add {product['name']}")
        prompt.geometry("460x560")
        prompt.resizable(False, False)
        prompt.configure(fg_color=BG_MAIN)

        # ═════════════════════════════════════════
        # BUTTONS FIRST — pinned to bottom
        # ═════════════════════════════════════════

        def save():
            try:
                qty = int(qty_e.get())
                if qty <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Enter a valid quantity.")
                return

            try:
                pieces = int(pieces_e.get() or 1)
                if pieces <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Error",
                    "Pieces per unit must be a positive number."
                )
                return

            chosen_unit = unit_var.get()

            self.cart.append({
                "product_id":      product["product_id"],
                "name":            product["name"],
                "code":            product["product_code"],
                "size":            product.get("size") or "",
                "unit":            chosen_unit,
                "pieces_per_unit": pieces,
                "category_name":   product.get("category_name") or "",
                "stock_qty":       stock_qty,
                "quantity":        qty,
                "cost":            float(product["price"]),
            })
            prompt.destroy()
            self._render_lines()

        btn_row = ctk.CTkFrame(prompt, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=30, pady=(8, 20))

        ctk.CTkButton(btn_row, text="Add",
                      height=40,
                      corner_radius=8,
                      font=font_bold(13),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=save).pack(fill="x")

        # ═════════════════════════════════════════
        # HEADER
        # ═════════════════════════════════════════

        ctk.CTkLabel(prompt, text=product["name"],
                     font=font_bold(14),
                     text_color=FG_PRIMARY).pack(pady=(20, 4))

        ctk.CTkLabel(prompt, text=product["product_code"],
                     font=font(11),
                     text_color=FG_SECONDARY).pack(pady=(0, 4))

        info_parts = []
        if product.get("size"):
            info_parts.append(f"Size: {product['size']}")
        if product.get("unit"):
            info_parts.append(f"Unit: {product['unit']}")
        if product.get("category_name"):
            info_parts.append(f"Cat: {product['category_name']}")
        if info_parts:
            ctk.CTkLabel(prompt, text="  •  ".join(info_parts),
                         font=font(10),
                         text_color=FG_MUTED).pack(pady=(0, 4))

        stock_qty = (product.get("stock_qty", 0)
                     if hasattr(product, "get") else product["stock_qty"])
        ctk.CTkLabel(prompt, text=f"Current Stock: {stock_qty}",
                     font=font_bold(11),
                     text_color=SUCCESS if stock_qty > 0 else DANGER).pack(pady=(0, 14))

        # ═════════════════════════════════════════
        # QUANTITY / UNIT
        # ═════════════════════════════════════════

        ctk.CTkLabel(prompt, text="QUANTITY / UNIT",
                     font=font_bold(10),
                     text_color=FG_SECONDARY).pack(anchor="w", padx=30, pady=(0, 4))

        qty_unit_row = ctk.CTkFrame(prompt, fg_color="transparent")
        qty_unit_row.pack(fill="x", padx=30)

        qty_e = ctk.CTkEntry(qty_unit_row, height=36,
                             corner_radius=8,
                             font=font(12),
                             fg_color=BG_INPUT,
                             border_color=BORDER,
                             border_width=1)
        qty_e.pack(side="left", fill="x", expand=True, padx=(0, 8))
        qty_e.insert(0, "1")

        default_unit = product.get("unit") or "pc"
        if default_unit not in UNIT_OPTIONS:
            default_unit = "pc"

        unit_var = ctk.StringVar(value=default_unit)
        unit_menu = ctk.CTkOptionMenu(
            qty_unit_row,
            values=UNIT_OPTIONS,
            variable=unit_var,
            width=100,
            height=36,
            corner_radius=8,
            font=font(12),
            fg_color=BG_INPUT,
            button_color=BG_INPUT,
            button_hover_color=NEUTRAL,
            text_color=FG_PRIMARY,
        )
        unit_menu.pack(side="left")

        # ═════════════════════════════════════════
        # PIECES PER UNIT
        # ═════════════════════════════════════════

        ctk.CTkLabel(prompt, text="PIECES PER UNIT",
                     font=font_bold(10),
                     text_color=FG_SECONDARY).pack(anchor="w", padx=30, pady=(12, 4))

        pieces_e = ctk.CTkEntry(prompt, height=36,
                                corner_radius=8,
                                font=font(12),
                                fg_color=BG_INPUT,
                                border_color=BORDER,
                                border_width=1)
        pieces_e.pack(fill="x", padx=30)
        pieces_e.insert(0, "1")

        ctk.CTkLabel(prompt,
                     text="How many pieces are inside 1 unit? (e.g. 12 for a case)",
                     font=font(9),
                     text_color=FG_MUTED).pack(anchor="w", padx=30, pady=(2, 0))

        # ---- Auto-lock to 1 when unit is 'pc' ----
        def _on_unit_change(choice=None):
            if unit_var.get() == "pc":
                pieces_e.delete(0, "end")
                pieces_e.insert(0, "1")
                pieces_e.configure(state="disabled")
            else:
                pieces_e.configure(state="normal")

        unit_var.trace_add("write", lambda *a: _on_unit_change())
        _on_unit_change()

        # ═════════════════════════════════════════
        # SHOW / FOCUS
        # ═════════════════════════════════════════

        prompt.update_idletasks()

        # ---- Bind to THIS dialog (the PO dialog), not the main app ----
        prompt.transient(self)
        prompt.grab_set()
        prompt.lift()
        prompt.focus_force()

        # ---- Center on the PO dialog itself ----
        prompt.after(10, lambda: prepare_dialog_screen(prompt, self))

    # ─────────────────────────────────────────────
    # RENDER LINES
    # ─────────────────────────────────────────────

    def _render_lines(self):
        for w in self.lines_frame.winfo_children():
            w.destroy()

        if not self.cart:
            ctk.CTkLabel(self.lines_frame,
                         text="No items yet",
                         font=font(11),
                         text_color=FG_MUTED).pack(pady=20)
            self.total_label.configure(text="₱0.00")
            return

        for i, line in enumerate(self.cart):
            bg = BG_ROW_ALT if i % 2 else BG_CARD

            row = ctk.CTkFrame(self.lines_frame, fg_color=bg, corner_radius=6)
            row.pack(fill="x", pady=2)

            # ---- ✕ remove (packed right) ----
            ctk.CTkButton(row, text="✕", width=32, height=28,
                          corner_radius=6,
                          font=font_bold(11),
                          fg_color=DANGER, hover_color="#DC2626",
                          command=lambda pid=line["product_id"]:
                              self._remove_line(pid)
                          ).pack(side="right", padx=(4, 6), pady=4)

            # ---- Name ----
            ctk.CTkLabel(row, text=line["name"], width=140,
                         anchor="w",
                         font=font_bold(11),
                         text_color=FG_PRIMARY).pack(side="left", padx=(6, 2), pady=6)

            # ---- Size ----
            ctk.CTkLabel(row, text=line.get("size") or "-",
                         width=60,
                         anchor="w",
                         font=font(10),
                         text_color=FG_SECONDARY).pack(side="left", padx=2)

            # ---- Qty + Unit + (pieces) ----
            qty_unit = f"{line['quantity']} {line.get('unit') or 'pc'}"
            pieces = line.get("pieces_per_unit") or 1
            if pieces > 1:
                total_pcs = line["quantity"] * pieces
                qty_unit += f" ({total_pcs} pc)"

            ctk.CTkLabel(row, text=qty_unit,
                         width=160,
                         anchor="w",
                         font=font(11),
                         text_color=FG_SECONDARY).pack(side="left", padx=2)

        total = sum(l["quantity"] * l["cost"] for l in self.cart)
        self.total_label.configure(text=f"₱{total:.2f}")

    def _remove_line(self, product_id):
        self.cart = [l for l in self.cart if l["product_id"] != product_id]
        self._render_lines()

    def _clear(self):
        self.cart.clear()
        self._render_lines()

    # ─────────────────────────────────────────────
    # SAVE
    # ─────────────────────────────────────────────

    def _save(self):
        if not self.cart:
            messagebox.showerror("Error", "Add at least one product to the order.")
            return

        supplier_id = self._get_selected_supplier_id()
        if supplier_id is None:
            messagebox.showerror("Error", "Please select a supplier.")
            return

        items = [{
            "product_id":      l["product_id"],
            "quantity":        l["quantity"],
            "unit":            l["unit"],
            "pieces_per_unit": l.get("pieces_per_unit", 1),
            "cost":            l["cost"],
            "expiration_date": None,
        } for l in self.cart]

        ok, result = PurchaseController.create(
            self.user, supplier_id, items, self.notes_e.get().strip()
        )
        if ok:
            messagebox.showinfo("Purchase Order Created",
                                f"PO #{result} created with {len(items)} item(s).")
            self.on_save()
            self.destroy()
        else:
            messagebox.showerror("Error", result)