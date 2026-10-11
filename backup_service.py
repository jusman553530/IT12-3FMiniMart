# ─────────────────────────────────────────────
# AUTOMATIC DATABASE BACKUP SERVICE
# ─────────────────────────────────────────────
#
# Creates a consistent snapshot of the SQLite database using
# sqlite3.Connection.backup(), which is safe to run while the app is
# writing. Plain file copies of a WAL-mode database can corrupt the
# backup — this avoids that.
#
# Schedule:
#   - On app start, if today's backup doesn't exist yet, create it.
#   - While running, check every CHECK_INTERVAL_SECONDS. If the date
#     has changed since the last backup, create a new one.
#   - Keep the most recent KEEP_DAYS backups. Delete older ones.
#
# Failure handling: never raises. Logs to console and returns a status.

import os
import sqlite3
import threading
from datetime import datetime, date, timedelta

from config import DB_PATH


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")
KEEP_DAYS = 30                     # how many days of backups to keep
CHECK_INTERVAL_SECONDS = 30 * 60   # check every 30 minutes while running

# Don't back up a database that has no real data in it yet.
MIN_PRODUCTS_FOR_BACKUP = 1


# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────

_lock = threading.Lock()
_timer = None
_last_backup_path = None
_last_backup_time = None
_last_backup_error = None


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def get_status():
    """Return a dict describing the last backup attempt."""
    with _lock:
        return {
            "path": _last_backup_path,
            "time": _last_backup_time,
            "error": _last_backup_error,
        }


def start_scheduler():
    """
    Start the background backup scheduler. Call once from main.py after
    initialize_database().
    """
    _backup_check()
    _schedule_next()


def stop_scheduler():
    """Cancel the pending timer. Call on app shutdown."""
    global _timer
    with _lock:
        if _timer is not None:
            try:
                _timer.cancel()
            except Exception:
                pass
            _timer = None


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _schedule_next():
    global _timer
    with _lock:
        _timer = threading.Timer(CHECK_INTERVAL_SECONDS, _on_timer_tick)
        _timer.daemon = True
        _timer.start()


def _on_timer_tick():
    _backup_check()
    _schedule_next()


def _backup_check():
    """
    If today's backup is missing, create one. Then prune old backups.
    Never raises — errors go into _last_backup_error.
    """
    global _last_backup_path, _last_backup_time, _last_backup_error

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # ---- Skip if the source DB has no meaningful data ----
        if not _has_data_to_back_up():
            with _lock:
                _last_backup_error = None
            return

        # ---- If today's backup already exists, nothing to do ----
        today_prefix = date.today().strftime("%Y-%m-%d")
        existing = _find_backup_for_date(today_prefix)
        if existing is not None:
            with _lock:
                _last_backup_path = existing
                _last_backup_time = _extract_timestamp(existing)
                _last_backup_error = None
            return

        # ---- Create a fresh backup ----
        path = _make_backup()

        with _lock:
            _last_backup_path = path
            _last_backup_time = datetime.now()
            _last_backup_error = None

        _prune_old_backups()

    except Exception as e:
        with _lock:
            _last_backup_error = str(e)
        print(f"[Backup] Failed: {e}")


def _has_data_to_back_up():
    """
    True if the database has at least one product. Prevents overwriting
    good backups with an empty DB after reset_db.py runs.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM products"
            ).fetchone()
            return (row[0] if row else 0) >= MIN_PRODUCTS_FOR_BACKUP
        finally:
            conn.close()
    except Exception:
        return False


def _find_backup_for_date(yyyy_mm_dd):
    """Return the path of a backup file whose name starts with the date."""
    if not os.path.isdir(BACKUP_DIR):
        return None
    prefix = f"store_data_{yyyy_mm_dd}"
    for name in os.listdir(BACKUP_DIR):
        if name.startswith(prefix) and name.endswith(".db"):
            return os.path.join(BACKUP_DIR, name)
    return None


def _extract_timestamp(path):
    """Parse the HHMMSS portion of the filename to a datetime."""
    try:
        base = os.path.basename(path)
        stamp = base.replace("store_data_", "").replace(".db", "")
        return datetime.strptime(stamp, "%Y-%m-%d_%H%M%S")
    except Exception:
        return None


def _make_backup():
    """
    Copy the live DB to a timestamped file using SQLite's backup API.
    Safe to run concurrently with writes.
    """
    now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest_path = os.path.join(BACKUP_DIR, f"store_data_{now_str}.db")

    source = sqlite3.connect(DB_PATH, timeout=10)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
            dest.commit()
        finally:
            dest.close()
    finally:
        source.close()

    return dest_path


def _prune_old_backups():
    """Delete backups older than KEEP_DAYS."""
    if not os.path.isdir(BACKUP_DIR):
        return

    cutoff = date.today() - timedelta(days=KEEP_DAYS)

    for name in os.listdir(BACKUP_DIR):
        if not (name.startswith("store_data_") and name.endswith(".db")):
            continue

        try:
            stamp = name.replace("store_data_", "").replace(".db", "")
            file_date = datetime.strptime(stamp[:10], "%Y-%m-%d").date()
        except Exception:
            continue

        if file_date < cutoff:
            try:
                os.remove(os.path.join(BACKUP_DIR, name))
            except Exception as e:
                print(f"[Backup] Could not delete {name}: {e}")