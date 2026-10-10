# ─────────────────────────────────────────────
# UI UTILITIES (window centering, dialogs, maximize)
# ─────────────────────────────────────────────

import sys
import os
import shutil
import uuid
import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime as _dt


# ─────────────────────────────────────────────
# IMAGE UTILITIES (product picture handling)
# ─────────────────────────────────────────────

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "product_images")
os.makedirs(IMAGE_DIR, exist_ok=True)


def pick_image_file():
    path = filedialog.askopenfilename(
        title="Select Product Image",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("All files", "*.*"),
        ]
    )
    return path or None


def save_product_image(source_path):
    if not source_path or not os.path.exists(source_path):
        return None

    ext = os.path.splitext(source_path)[1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(IMAGE_DIR, filename)

    shutil.copy2(source_path, dest)
    return dest


def delete_product_image(image_path):
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass


# ─────────────────────────────────────────────
# WINDOW SIZING HELPERS
# ─────────────────────────────────────────────

def _requested_size(window):
    """
    Return (w, h) from the window's declared geometry string,
    parsed as ints. If parsing fails, fall back to winfo reqwidth/reqheight.
    """
    try:
        geom = window.geometry()           # e.g. "520x620+100+100"
        size_part = geom.split("+")[0].split("-")[0]
        w_str, h_str = size_part.split("x")
        return int(w_str), int(h_str)
    except Exception:
        return window.winfo_reqwidth(), window.winfo_reqheight()


def center_on_parent(window, parent):
    """
    Center a pop-up window on its parent window.
    Call AFTER widgets are built.

    Uses the declared geometry (from .geometry("WxH")) rather than the
    current rendered size — Tk reports 200x200 for windows that haven't
    finished laying out yet, which used to collapse dialogs.
    """
    window.update_idletasks()

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()

    win_w, win_h = _requested_size(window)

    x = parent_x + (parent_w - win_w) // 2
    y = parent_y + (parent_h - win_h) // 2

    # Keep inside screen bounds
    if x < 0: x = 0
    if y < 0: y = 0

    window.geometry(f"{win_w}x{win_h}+{x}+{y}")


def center_on_screen(window):
    """
    Center a pop-up window on the screen.

    Uses the declared geometry (from .geometry("WxH")) rather than the
    current rendered size — see note in center_on_parent().
    """
    window.update_idletasks()

    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    win_w, win_h = _requested_size(window)

    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 2

    if x < 0: x = 0
    if y < 0: y = 0

    window.geometry(f"{win_w}x{win_h}+{x}+{y}")


# ─────────────────────────────────────────────
# MAXIMIZE (cross-platform)
# ─────────────────────────────────────────────

def maximize(window):
    if sys.platform.startswith("win"):
        window.state("zoomed")
    elif sys.platform == "darwin":
        window.attributes("-zoomed", True)
    else:
        window.attributes("-zoomed", True)


# ─────────────────────────────────────────────
# DIALOG SETUP
# ─────────────────────────────────────────────

def prepare_dialog(dialog, parent):
    """
    Setup a CTkToplevel tied to parent and centered on it.
    """
    dialog.transient(parent)
    dialog.lift()
    dialog.grab_set()
    dialog.focus_force()

    dialog.after(10, lambda: center_on_parent(dialog, parent))


def prepare_dialog_screen(dialog, parent):
    """
    Same as prepare_dialog(), but centers on the SCREEN instead.
    """
    dialog.transient(parent)
    dialog.lift()
    dialog.grab_set()
    dialog.focus_force()

    dialog.after(10, lambda: center_on_screen(dialog))


def make_dialog(parent, title="Dialog", size="400x400", resizable=(False, False)):
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry(size)
    dialog.resizable(*resizable)
    return dialog


def ui_date_to_db(text):
    """
    Convert a UI date string 'MM/DD/YYYY' → 'YYYY-MM-DD'.
    Returns None for empty or invalid input.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return _dt.strptime(text, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def db_date_to_ui(text):
    """
    Convert a DB date string 'YYYY-MM-DD' → 'MM/DD/YYYY'.
    Returns "" for empty or invalid input.
    """
    text = (text or "").strip()
    if not text:
        return ""
    try:
        return _dt.strptime(text, "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        return ""


def is_valid_ui_date(text):
    """True if text is a valid 'MM/DD/YYYY' date."""
    text = (text or "").strip()
    if not text:
        return False
    try:
        _dt.strptime(text, "%m/%d/%Y")
        return True
    except ValueError:
        return False