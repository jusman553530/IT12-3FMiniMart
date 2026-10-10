# ─────────────────────────────────────────────
# PURCHASE MODEL
# ─────────────────────────────────────────────

from database import get_connection, now_local
from models.batch_model import create_batch_cur


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _full_name_sql(alias="u"):
    return (
        f"TRIM("
        f"COALESCE({alias}.first_name, '') || ' ' || "
        f"COALESCE({alias}.middle_name || ' ', '') || "
        f"COALESCE({alias}.last_name, '')"
        f") AS full_name"
    )


# ─────────────────────────────────────────────
# WRITE
# ─────────────────────────────────────────────

def create_purchase(supplier_id, user_id, items, notes=""):
    """
    Create a Purchase Order (status = 'Ordered').

    items = list of dicts:
        {
          product_id: int,
          quantity:   int,
          unit:       str,      # 'pc', 'pack', 'box', 'case', 'sack', 'kg', 'L'
          pieces_per_unit: int | None,
          expiration_date: str | None
        }

    Per-line cost tracking has been removed. purchases.total_cost
    starts at 0 and is set later when the PO is received.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchases
                (supplier_id, user_id, total_cost, status, notes, created_at)
            VALUES (?, ?, 0, 'Ordered', ?, ?)
        """, (supplier_id, user_id, notes, now_local()))
        pid = cur.lastrowid

        for i in items:
            cur.execute("""
                INSERT INTO purchase_items
                    (purchase_id, product_id, quantity, unit,
                     pieces_per_unit, cost, expiration_date,
                     received_quantity)
                VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
            """, (pid, i["product_id"], i["quantity"],
                  i.get("unit"),
                  i.get("pieces_per_unit") or 1,
                  i.get("expiration_date")))

        conn.commit()
        return True, pid

    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def receive_purchase(purchase_id, user_id, received_quantities=None,
                     product_ids=None, total_amount=None):
    """
    Mark a PO as received (fully or partially), create batches, and
    store the user-entered PO total.

    Parameters
    ----------
    purchase_id : int
    user_id : int
    received_quantities : dict[int, int] | None
        Maps product_id → received quantity (pieces).
        If None, defaults to each line's ordered `quantity`.
    product_ids : list[int] | None
        Legacy: receive only these product_ids at their ordered qty.
        Ignored if received_quantities is provided.
    total_amount : float | None
        If provided, saves this to purchases.total_cost.

    Returns
    -------
    (ok, message) : tuple[bool, str]
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # ---- 1. Load PO ----
        row = cur.execute(
            "SELECT status, supplier_id FROM purchases WHERE purchase_id = ?",
            (purchase_id,)
        ).fetchone()

        if not row:
            return False, "Purchase not found."
        if row["status"] != "Ordered":
            return False, f"Purchase is already '{row['status']}'."

        supplier_id = row["supplier_id"]

        # ---- 2. Load all items ----
        all_items = cur.execute("""
            SELECT product_id, quantity, expiration_date, unit
            FROM purchase_items
            WHERE purchase_id = ?
        """, (purchase_id,)).fetchall()

        if not all_items:
            return False, "Purchase has no items."

        # ---- 3. Decide which items get received + their quantities ----
        if received_quantities is not None:
            items_to_receive = []
            for it in all_items:
                pid = it["product_id"]
                if pid not in received_quantities:
                    continue
                qty = received_quantities[pid]
                if qty is None or qty <= 0:
                    continue
                items_to_receive.append((it, qty))

        elif product_ids is not None:
            wanted = set(product_ids)
            items_to_receive = [
                (it, it["quantity"])
                for it in all_items
                if it["product_id"] in wanted
            ]

        else:
            items_to_receive = [(it, it["quantity"]) for it in all_items]

        if not items_to_receive:
            return False, "No items selected to receive."

        # ---- 4. Create batches + record received quantity ----
        # Batches are created with cost_price = 0 (no line cost tracking).
        for item, qty in items_to_receive:
            create_batch_cur(
                cur,
                product_id=item["product_id"],
                quantity=qty,
                cost_price=0,
                expiration_date=item["expiration_date"],
                supplier_id=supplier_id,
                purchase_id=purchase_id,
            )

            cur.execute("""
                UPDATE purchase_items
                SET received_quantity = ?
                WHERE purchase_id = ? AND product_id = ?
            """, (qty, purchase_id, item["product_id"]))

        # ---- 5. Save the PO total (if provided) ----
        if total_amount is not None:
            cur.execute("""
                UPDATE purchases
                SET total_cost = ?
                WHERE purchase_id = ?
            """, (float(total_amount), purchase_id))

        # ---- 6. Mark as Received if every line got some amount ----
        handled = cur.execute("""
            SELECT COUNT(*) AS c
            FROM purchase_items
            WHERE purchase_id = ? AND received_quantity IS NOT NULL
        """, (purchase_id,)).fetchone()["c"]

        total_lines = len(all_items)

        if handled >= total_lines:
            cur.execute("""
                UPDATE purchases
                SET status = 'Received', received_at = ?
                WHERE purchase_id = ?
            """, (now_local(), purchase_id))
            msg = "Purchase fully received. Batches created."
        else:
            msg = (
                f"Partially received {handled} of {total_lines} item(s). "
                f"Remaining items can still be received later."
            )

        conn.commit()
        return True, msg

    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def cancel_purchase(purchase_id):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE purchases SET status = 'Cancelled'
            WHERE purchase_id = ? AND status = 'Ordered'
        """, (purchase_id,))
        conn.commit()
        return True, "Purchase cancelled."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────

def get_all_purchases(status=None, supplier_id=None):
    conn = get_connection()
    sql = f"""
        SELECT pu.*,
               s.name AS supplier_name,
               u.username, {_full_name_sql('u')}
        FROM purchases pu
        JOIN suppliers s ON pu.supplier_id = s.supplier_id
        JOIN users u     ON pu.user_id     = u.user_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND pu.status = ?"
        params.append(status)
    if supplier_id:
        sql += " AND pu.supplier_id = ?"
        params.append(supplier_id)
    sql += " ORDER BY pu.created_at DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_purchase(purchase_id):
    conn = get_connection()
    row = conn.execute(f"""
        SELECT pu.*,
               s.name AS supplier_name,
               u.username, {_full_name_sql('u')}
        FROM purchases pu
        JOIN suppliers s ON pu.supplier_id = s.supplier_id
        JOIN users u     ON pu.user_id     = u.user_id
        WHERE pu.purchase_id = ?
    """, (purchase_id,)).fetchone()
    conn.close()
    return row


def get_purchase_items(purchase_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT pi.*,
               p.name AS product_name,
               p.product_code,
               p.size AS product_size,
               p.unit AS product_unit
        FROM purchase_items pi
        JOIN products p ON pi.product_id = p.product_id
        WHERE pi.purchase_id = ?
    """, (purchase_id,)).fetchall()
    conn.close()
    return rows


def get_purchases_by_supplier(supplier_id):
    return get_all_purchases(supplier_id=supplier_id)