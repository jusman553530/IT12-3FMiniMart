# ─────────────────────────────────────────────
# RECEIPT DIALOG
# ─────────────────────────────────────────────

import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import messagebox

from utils import prepare_dialog_screen
from config import (
    font, font_bold,
    BG_MAIN, BG_CARD, BORDER,
    FG_PRIMARY, FG_SECONDARY,
    BRAND_GREEN,
    NEUTRAL, NEUTRAL_HOVER, NEUTRAL_TEXT,
)

# ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ─────────────────────────────────────────────
# RECEIPTS FOLDER
# ─────────────────────────────────────────────

RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "receipts")
RECEIPTS_DIR = os.path.abspath(RECEIPTS_DIR)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# ⚡ AUTO-INCREMENT FILENAME HELPER
# ─────────────────────────────────────────────

def _next_free_path(path):
    """If `path` already exists, return 'path_2.pdf', 'path_3.pdf', etc."""
    if not os.path.exists(path):
        return path

    folder = os.path.dirname(path)
    base, ext = os.path.splitext(os.path.basename(path))

    n = 2
    while True:
        candidate = os.path.join(folder, f"{base}_{n}{ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


# ─────────────────────────────────────────────
# RECEIPT DIALOG
# ─────────────────────────────────────────────

class ReceiptDialog(ctk.CTkToplevel):

    WIDTH = 42
    MONO_FONT = ("Consolas", 12)

    def __init__(self, parent, txn_id, user, cart,
                 payment_method, amount_paid, change, total,
                 gcash_reference=None, created_at=None):
        super().__init__(parent)
        self.parent = parent
        self.txn_id = txn_id
        self.user = user
        self.cart = cart
        self.payment_method = payment_method
        self.amount_paid = amount_paid
        self.change = change
        self.total = total
        self.gcash_reference = gcash_reference
        self.created_at = created_at

        self.title(f"Receipt #{txn_id}")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        self._build()

        # Set final size AFTER widgets are built so winfo_reqheight is accurate
        self.update_idletasks()
        self._fit_to_content()

        prepare_dialog_screen(self, self.parent)

        self.transient(parent)
        self.grab_set()
        self.focus_force()

    # ─────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────

    def _build(self):
        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(header, text="Receipt",
                     font=font_bold(15),
                     text_color=FG_PRIMARY,
                     anchor="w").pack(side="left")

        ctk.CTkButton(header, text="✕",
                      width=30, height=30,
                      corner_radius=6,
                      font=font_bold(13),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self.destroy).pack(side="right")

        ctk.CTkLabel(self,
                     text=f"Transaction #{self.txn_id} completed",
                     font=font(11),
                     text_color=FG_SECONDARY,
                     anchor="w").pack(fill="x", padx=16, pady=(0, 8))

        # ---- Receipt body ----
        card = ctk.CTkFrame(self, fg_color="#FFFFFF",
                            corner_radius=8,
                            border_width=1,
                            border_color=BORDER)
        card.pack(padx=16, pady=(0, 10))

        receipt_text = self._render_receipt_text()

        self.receipt_label = ctk.CTkLabel(
            card,
            text=receipt_text,
            font=self.MONO_FONT,
            text_color="#000000",
            justify="left",
            anchor="nw",
        )
        self.receipt_label.pack(padx=14, pady=14)

        # ---- Buttons ----
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(btn_row, text="Close",
                      width=120, height=40,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER,
                      text_color=NEUTRAL_TEXT,
                      command=self.destroy
                      ).pack(side="left")

        ctk.CTkButton(btn_row, text="Print",
                      height=40,
                      corner_radius=8,
                      font=font_bold(12),
                      fg_color=BRAND_GREEN, hover_color="#1E9040",
                      command=self._print_receipt
                      ).pack(side="right", fill="x", expand=True, padx=(8, 0))

    # ─────────────────────────────────────────────
    # AUTO-SIZE — snug fit
    # ─────────────────────────────────────────────

    def _fit_to_content(self):
        self.update_idletasks()

        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()

        window_w = req_w + 8
        window_h = req_h + 8

        window_w = max(window_w, 520)
        window_h = max(window_h, 380)

        self.geometry(f"{window_w}x{window_h}")
        self.minsize(window_w, window_h)

    # ─────────────────────────────────────────────
    # RECEIPT TEXT BUILDER (on-screen preview)
    # ─────────────────────────────────────────────

    def _render_receipt_text(self):
        w = self.WIDTH
        lines = []

        def center(text):
            return text.center(w)

        def divider():
            return "=" * w

        def thin_divider():
            return "-" * w

        lines.append(divider())
        lines.append(center("3F MiniMart"))
        lines.append(divider())

        lines.append(f"Receipt #: {self.txn_id}".ljust(w))
        if self.created_at:
            lines.append(f"Date     : {self.created_at}".ljust(w))
        cashier = (self.user.get("full_name")
                   or self.user.get("username")
                   or "-")
        lines.append(f"Cashier  : {cashier}".ljust(w))
        lines.append(thin_divider())

        lines.append(
            "ITEM".ljust(20)
            + "QTY".rjust(5)
            + "PRICE".rjust(9)
            + "TOTAL".rjust(8)
        )
        lines.append(thin_divider())

        for item in self.cart:
            name = item["name"]
            if item.get("brand"):
                name = f"{item['brand']} {name}"
            if item.get("size"):
                name = f"{name} {item['size']}"

            qty = item["quantity"]
            price = item["price"]
            subtotal = price * qty

            display = name[:20] if len(name) > 20 else name
            rest = name[20:] if len(name) > 20 else ""

            lines.append(
                display.ljust(20)
                + f"{qty}".rjust(5)
                + f"₱{price:.2f}".rjust(9)
                + f"₱{subtotal:.2f}".rjust(8)
            )

            if rest:
                lines.append(("    " + rest).ljust(w))

        lines.append(thin_divider())

        lines.append("Subtotal:".ljust(28) + f"₱{self.total:.2f}".rjust(14))
        lines.append(f"Payment: {self.payment_method}".ljust(w))

        if self.payment_method == "GCash" and self.gcash_reference:
            lines.append(f"GCash Ref: {self.gcash_reference}".ljust(w))

        lines.append("Amount Paid:".ljust(28) + f"₱{self.amount_paid:.2f}".rjust(14))
        lines.append("Change:".ljust(28) + f"₱{self.change:.2f}".rjust(14))

        lines.append(divider())
        lines.append(center("Thank you for your purchase!"))
        lines.append(center("Please come again"))
        lines.append(divider())

        return "\n".join(lines)

    # ─────────────────────────────────────────────
    # ⚡ PRINT — generate PDF, then open the Windows print dialog
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ PRINT — generate PDF, then open the print dialog
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ PRINT — generate PDF, then open the print dialog
    # ─────────────────────────────────────────────

    def _print_receipt(self):
        # ---- 1. Build the PDF path (auto-incremented) ----
        base_name = f"receipt_{self.txn_id:06d}.pdf"
        path = os.path.join(RECEIPTS_DIR, base_name)
        path = _next_free_path(path)

        # ---- 2. Generate the PDF ----
        try:
            self._build_receipt_pdf(path)
        except Exception as e:
            messagebox.showerror(
                "Print Failed",
                f"Could not generate receipt PDF:\n{e}",
                parent=self,
            )
            return

        # ---- 3. Hand it to the OS with a print-aware launcher ----
        if sys.platform.startswith("win"):
            if self._launch_print_windows(path):
                return

            # Nothing worked — save-and-tell fallback
            try:
                subprocess.Popen(["explorer", "/select,", path])
            except Exception:
                pass

            messagebox.showinfo(
                "Receipt Saved",
                "Could not open the print dialog automatically.\n\n"
                f"The receipt PDF was saved to:\n{path}\n\n"
                "Open it manually and press Ctrl+P to print.",
                parent=self,
            )
            return

        # macOS / Linux
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror(
                "Print Failed",
                f"Could not open receipt:\n{e}\n\n"
                f"PDF saved at:\n{path}",
                parent=self,
            )

    # ─────────────────────────────────────────────
    # ⚡ WINDOWS LAUNCHER — tries several print verbs
    # ─────────────────────────────────────────────

    def _launch_print_windows(self, path):
        """
        Try to open `path` in an app that will show the print dialog.

        Order of attempts:
          1. os.startfile(path, "print")  — works if the default .pdf handler
             registers a 'print' verb (Adobe Reader does).
          2. Edge with --print  — Edge ships with Windows and honors this flag,
             which opens the PDF and triggers the print dialog immediately.
          3. Chrome with --print — same idea, for machines where Chrome is
             installed but Edge isn't the default.
        Returns True on success, False if every attempt failed.
        """

        # ---- Attempt 1: default print verb ----
        try:
            os.startfile(path, "print")
            return True
        except OSError:
            pass

        # ---- Attempt 2: Microsoft Edge ----
        edge_paths = [
            # 64-bit Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            # 32-bit Edge
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            # Per-user install
            os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"
            ),
        ]
        for edge in edge_paths:
            if os.path.exists(edge):
                try:
                    subprocess.Popen([edge, "--print", path])
                    return True
                except Exception:
                    pass

        # ---- Attempt 3: Google Chrome ----
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
            ),
        ]
        for chrome in chrome_paths:
            if os.path.exists(chrome):
                try:
                    subprocess.Popen([chrome, "--print", path])
                    return True
                except Exception:
                    pass

        return False
    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER (ReportLab — Helvetica/PHP)
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — monospace, matches the preview
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — monospace, matches the preview
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — fits within a printable page
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — thermal-receipt sized
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — thermal-receipt sized
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # ⚡ RECEIPT PDF BUILDER — thermal-receipt sized
    # ─────────────────────────────────────────────

    def _build_receipt_pdf(self, path):
        """
        Render the receipt PDF at thermal-receipt proportions.

        Uses a raw BaseDocTemplate + single Frame so the content
        exactly fills the page:
          - 80mm wide (standard thermal paper)
          - 6.5pt Courier
          - height measured from the actual flowable, plus a small
            safety buffer, so nothing gets pushed to a phantom page 2.
        """
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            BaseDocTemplate, Frame, PageTemplate, Preformatted,
        )

        receipt_text = self._render_receipt_text()
        receipt_text = receipt_text.replace("₱", "PHP")   # Courier lacks ₱

        style = _receipt_mono_style()

        # ---- Page geometry ----
        page_width = 80 * mm
        left_pad = 3 * mm
        right_pad = 3 * mm
        top_pad = 2 * mm
        bottom_pad = 2 * mm

        avail_width = page_width - left_pad - right_pad

        # ---- Measure the actual flowable height ----
        flowable = Preformatted(receipt_text, style)
        _, content_height = flowable.wrap(avail_width, 100000)

        # ---- Page height = content + padding + a real safety buffer ----
        # The buffer absorbs ReportLab's fractional rounding so the
        # last line never spills onto a second page.
        safety = 12   # points ≈ 4.2mm
        page_height = top_pad + content_height + bottom_pad + safety

        # ---- Build with BaseDocTemplate + single Frame ----
        # Frame starts at (0,0) local coords (bottom-left) and its
        # height exactly equals content_height + top_pad. No internal
        # margins, so the flowable fits with room to spare.
        doc = BaseDocTemplate(
            path,
            pagesize=(page_width, page_height),
            leftMargin=0,
            rightMargin=0,
            topMargin=0,
            bottomMargin=0,
            title=f"Receipt #{self.txn_id}",
            author="3F MiniMart POS",
        )

        frame = Frame(
            x1=left_pad,
            y1=bottom_pad,          # distance from page bottom
            width=avail_width,
            height=page_height - top_pad - bottom_pad,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            showBoundary=0,
        )

        doc.addPageTemplates([PageTemplate(id="receipt", frames=[frame])])
        doc.build([flowable])
# ─────────────────────────────────────────────
# ⚡ RECEIPT MONOSPACE STYLE (module level)
# ─────────────────────────────────────────────

def _receipt_mono_style():
    """
    Style for the monospace receipt body.

    6.5pt Courier: 42 chars ≈ 42 × 3.9pt ≈ 164pt ≈ 58mm — comfortably
    inside the ~74mm usable width on an 80mm page.
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    return ParagraphStyle(
        "receipt_mono",
        fontName="Courier",
        fontSize=6.5,
        leading=8,
        textColor=colors.black,
        alignment=0,
    )