# ─────────────────────────────────────────────
# DATABASE SETUP (SQLite — batch-tracked inventory)
# ─────────────────────────────────────────────

import sqlite3
import datetime
import threading
from config import DB_PATH, ROLE_ADMIN


# ─────────────────────────────────────────────
# LOCAL TIME HELPER
# ─────────────────────────────────────────────

def now_local():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
# SHARED CONNECTION — one per thread, wrapped so
# that .close() is a no-op. Existing model files
# call conn.close() everywhere; that stays safe.
# ─────────────────────────────────────────────

_local = threading.local()


class _SharedConnection:
    """Wraps a real sqlite3.Connection so .close() does nothing.

    The app opens a fresh connection in every model function and closes
    it immediately after. Opening a SQLite file is expensive on Windows
    (file lock, WAL header check, PRAGMA setup), and doing it hundreds of
    times per screen was the source of multi-second lag.

    This wrapper keeps ONE real connection alive per thread and turns
    every .close() into a no-op, so existing code that does:

        conn = get_connection()
        ...
        conn.close()

    keeps working unchanged, but never actually closes the handle.
    """

    __slots__ = ("_conn",)

    def __init__(self, real_conn):
        self._conn = real_conn

    # ---- Everything proxies to the real connection ----

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._conn.executescript(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self, *args, **kwargs):
        return self._conn.commit(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        return self._conn.rollback(*args, **kwargs)

    def close(self, *args, **kwargs):
        # ⚡ NO-OP — shared connection stays open
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Do NOT close on context exit either
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection():
    """Return the shared, thread-local SQLite connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        real = sqlite3.connect(DB_PATH, timeout=10,
                               check_same_thread=False)
        real.row_factory = sqlite3.Row
        real.execute("PRAGMA foreign_keys = ON")
        real.execute("PRAGMA journal_mode = WAL")
        real.execute("PRAGMA busy_timeout = 10000")
        real.execute("PRAGMA synchronous = NORMAL")
        real.execute("PRAGMA temp_store = MEMORY")
        conn = _SharedConnection(real)
        _local.conn = conn
    return conn


def close_connection():
    """Actually close the shared connection. Call at app shutdown."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn._conn.close()
        except Exception:
            pass
        _local.conn = None


# ─────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────

def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    # ---- 1. users ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            first_name   TEXT NOT NULL,
            middle_name  TEXT,
            last_name    TEXT NOT NULL,
            role         TEXT NOT NULL CHECK(role IN ('admin','staff')),
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT NOT NULL
        )
    """)

    # ---- 2. supplier_categories ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_categories (
            scat_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL
        )
    """)

    # ---- 3. suppliers ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            supplier_category_id INTEGER NOT NULL,
            contact_number       TEXT,
            contact_person_first TEXT,
            contact_person_middle TEXT,
            contact_person_last  TEXT,
            address              TEXT,
            is_archived          INTEGER DEFAULT 0,
            created_at           TEXT NOT NULL,
            FOREIGN KEY (supplier_category_id)
                REFERENCES supplier_categories(scat_id)
        )
    """)

    # ---- 4. categories ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL
        )
    """)

    # ---- 5. products ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code    TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            brand           TEXT,
            size            TEXT,
            unit            TEXT DEFAULT 'pc',
            cost_price      REAL DEFAULT 0,
            price           REAL NOT NULL,
            low_stock_level INTEGER DEFAULT 10,
            image_path      TEXT,
            is_archived     INTEGER DEFAULT 0,
            supplier_id     INTEGER NOT NULL,
            category_id     INTEGER NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    """)

    # ---- 6. batches ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            batch_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id      INTEGER NOT NULL,
            batch_no        TEXT NOT NULL,
            quantity        INTEGER NOT NULL DEFAULT 0,
            cost_price      REAL DEFAULT 0,
            expiration_date TEXT,
            supplier_id     INTEGER,
            purchase_id     INTEGER,
            is_archived     INTEGER DEFAULT 0,
            received_at     TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (product_id)  REFERENCES products(product_id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
            FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id)
        )
    """)

    # ---- 7. transactions ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            total            REAL NOT NULL,
            payment_method   TEXT NOT NULL CHECK(payment_method IN ('Cash','GCash')),
            amount_paid      REAL NOT NULL,
            change_due       REAL DEFAULT 0,
            gcash_reference  TEXT,
            created_at       TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # ---- 8. transaction_items ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transaction_items (
            item_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id  INTEGER NOT NULL,
            product_id      INTEGER NOT NULL,
            batch_id        INTEGER,
            quantity        INTEGER NOT NULL,
            price           REAL NOT NULL,
            cost_price      REAL DEFAULT 0,
            subtotal        REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
            FOREIGN KEY (product_id)     REFERENCES products(product_id),
            FOREIGN KEY (batch_id)       REFERENCES batches(batch_id)
        )
    """)

    # ---- 9. purchases ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            purchase_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id  INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            total_cost   REAL DEFAULT 0,
            status       TEXT NOT NULL DEFAULT 'Ordered'
                         CHECK(status IN ('Ordered','Received','Cancelled')),
            notes        TEXT,
            created_at   TEXT NOT NULL,
            received_at  TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
            FOREIGN KEY (user_id)     REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            pitem_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id        INTEGER NOT NULL,
            product_id         INTEGER NOT NULL,
            quantity           INTEGER NOT NULL,
            unit               TEXT,
            pieces_per_unit    INTEGER DEFAULT 1,
            cost               REAL NOT NULL,
            expiration_date    TEXT,
            received_quantity  INTEGER,
            FOREIGN KEY (purchase_id) REFERENCES purchases(purchase_id),
            FOREIGN KEY (product_id)  REFERENCES products(product_id)
        )
    """)

    # ---- 11. activity_logs ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            action      TEXT NOT NULL,
            details     TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # ---- 12. Indexes ----
    _create_indexes(cur)

    conn.commit()

    _run_migrations()
    _seed_default_admin()
    _seed_default_supplier_category()


# ─────────────────────────────────────────────
# INDEXES
# ─────────────────────────────────────────────

def _create_indexes(cur):
    index_sql = [
        "CREATE INDEX IF NOT EXISTS idx_batches_product ON batches(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_batches_expiration ON batches(expiration_date)",
        "CREATE INDEX IF NOT EXISTS idx_batches_archived ON batches(is_archived)",
        "CREATE INDEX IF NOT EXISTS idx_batches_product_active ON batches(product_id, is_archived, expiration_date)",

        "CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_products_archived ON products(is_archived)",

        "CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)",

        "CREATE INDEX IF NOT EXISTS idx_txn_items_transaction ON transaction_items(transaction_id)",
        "CREATE INDEX IF NOT EXISTS idx_txn_items_product ON transaction_items(product_id)",

        "CREATE INDEX IF NOT EXISTS idx_suppliers_category ON suppliers(supplier_category_id)",
        "CREATE INDEX IF NOT EXISTS idx_suppliers_archived ON suppliers(is_archived)",

        "CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id)",

        "CREATE INDEX IF NOT EXISTS idx_logs_created ON activity_logs(created_at)",
    ]
    for sql in index_sql:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass


# ─────────────────────────────────────────────
# MIGRATIONS (safe ALTER TABLE — for existing DBs)
# ─────────────────────────────────────────────

def _run_migrations():
    conn = get_connection()
    cur = conn.cursor()

    migrations = [
        ("ALTER TABLE suppliers ADD COLUMN supplier_category_id INTEGER",
         "suppliers.supplier_category_id"),
        ("ALTER TABLE suppliers ADD COLUMN is_archived INTEGER DEFAULT 0",
         "suppliers.is_archived"),
        ("ALTER TABLE suppliers ADD COLUMN contact_number TEXT",
         "suppliers.contact_number"),
        ("ALTER TABLE suppliers ADD COLUMN contact_person_first TEXT",
         "suppliers.contact_person_first"),
        ("ALTER TABLE suppliers ADD COLUMN contact_person_middle TEXT",
         "suppliers.contact_person_middle"),
        ("ALTER TABLE suppliers ADD COLUMN contact_person_last TEXT",
         "suppliers.contact_person_last"),

        ("ALTER TABLE products ADD COLUMN product_code TEXT",
         "products.product_code"),
        ("ALTER TABLE products ADD COLUMN image_path TEXT",
         "products.image_path"),
        ("ALTER TABLE products ADD COLUMN is_archived INTEGER DEFAULT 0",
         "products.is_archived"),
        ("ALTER TABLE products ADD COLUMN brand TEXT",
         "products.brand"),
        ("ALTER TABLE products ADD COLUMN size TEXT",
         "products.size"),
        ("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT 'pc'",
         "products.unit"),
        ("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0",
         "products.cost_price"),
        ("ALTER TABLE products ADD COLUMN expiration_date TEXT",
         "products.expiration_date"),
        ("ALTER TABLE products ADD COLUMN updated_at TEXT",
         "products.updated_at"),

        ("ALTER TABLE purchases ADD COLUMN status TEXT DEFAULT 'Ordered'",
         "purchases.status"),
        ("ALTER TABLE purchases ADD COLUMN notes TEXT",
         "purchases.notes"),
        ("ALTER TABLE purchases ADD COLUMN received_at TEXT",
         "purchases.received_at"),

        ("ALTER TABLE purchase_items ADD COLUMN unit TEXT",
         "purchase_items.unit"),
        ("ALTER TABLE purchase_items ADD COLUMN received_quantity INTEGER",
         "purchase_items.received_quantity"),

        ("ALTER TABLE transactions ADD COLUMN gcash_reference TEXT",
         "transactions.gcash_reference"),

        ("ALTER TABLE users ADD COLUMN first_name TEXT",  "users.first_name"),
        ("ALTER TABLE users ADD COLUMN middle_name TEXT", "users.middle_name"),
        ("ALTER TABLE users ADD COLUMN last_name TEXT",   "users.last_name"),
    ]

    for sql, name in migrations:
        try:
            cur.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass

    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(suppliers)")]
        if "contact" in cols:
            cur.execute("""
                UPDATE suppliers
                SET contact_number = contact
                WHERE contact_number IS NULL
                  AND contact IS NOT NULL
                  AND contact != ''
            """)
            conn.commit()
    except Exception:
        pass

    _create_indexes(cur)
    conn.commit()


# ─────────────────────────────────────────────
# SEED DATA
# ─────────────────────────────────────────────

def _seed_default_admin():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM users")
        if cur.fetchone()["c"] == 0:
            cur.execute("""
                INSERT INTO users
                    (username, password, first_name, middle_name, last_name,
                     role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("admin", "admin123", "Store", None, "Owner",
                  ROLE_ADMIN, now_local()))
            conn.commit()
            print("[DB] Default admin created -> username: admin | password: admin123")
    finally:
        pass  # ⚡ do NOT close — shared connection


def _seed_default_supplier_category():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM supplier_categories")
        if cur.fetchone()["c"] == 0:
            cur.execute("""
                INSERT INTO supplier_categories (name, description, created_at)
                VALUES (?, ?, ?)
            """, ("General", "Default supplier category", now_local()))
            conn.commit()
            print("[DB] Default supplier category created: General")
    finally:
        pass  # ⚡ do NOT close — shared connection