# ─────────────────────────────────────────────
# TRANSACTION CONTROLLER
# ─────────────────────────────────────────────

from models.transaction_model import (
    create_transaction, get_transactions_filtered,
    get_transaction_items, get_sales_summary,
)
from models.activity_log_model import log_action


class TransactionController:

    # ─────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────

    @staticmethod
    def create(user_id, cart, payment_method, amount_paid,
               gcash_reference=None):
        ok, result, change = create_transaction(
            user_id, cart, payment_method, amount_paid, gcash_reference
        )

        # ⚡ Log the sale on success
        if ok:
            try:
                total = sum(item["price"] * item["quantity"] for item in cart)
                item_count = sum(item["quantity"] for item in cart)
                log_action(
                    user_id,
                    "SALE",
                    f"Txn #{result} | {item_count} item(s) | "
                    f"₱{total:.2f} | {payment_method}",
                )
            except Exception as e:
                print(f"[SALE LOG] Failed: {e}")

        return ok, result, change

    # ─────────────────────────────────────────────
    # READ
    # ─────────────────────────────────────────────

    @staticmethod
    def list(date_from=None, date_to=None, search=None,
             payment_method=None):
        rows = get_transactions_filtered(
            date_from=date_from,
            date_to=date_to,
            search=search,
            payment_method=payment_method,
        )
        # Convert sqlite3.Row → dict so callers can use .get()
        return [dict(r) for r in rows]

    @staticmethod
    def items(transaction_id):
        rows = get_transaction_items(transaction_id)
        return [dict(r) for r in rows]

    @staticmethod
    def summary(date_from=None, date_to=None):
        return get_sales_summary(date_from=date_from, date_to=date_to)

    # ─────────────────────────────────────────────
    # PROFIT
    # ─────────────────────────────────────────────

    @staticmethod
    def profit(transaction_id):
        items = get_transaction_items(transaction_id)
        profit = 0.0
        for it in items:
            cost = it["cost_price"] if "cost_price" in it.keys() else 0
            profit += (it["price"] - (cost or 0)) * it["quantity"]
        return profit