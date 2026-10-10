# ─────────────────────────────────────────────
# DASHBOARD CONTROLLER
# ─────────────────────────────────────────────

from models.transaction_model import get_dashboard_stats
from models.product_model import get_all_products
from models.batch_model import (
    count_expiring_soon, count_expired,
)


class DashboardController:

    @staticmethod
    def get_stats():
        """
        Compute dashboard stats. Uses ONE product fetch for all
        product-derived numbers, and batch-level counts for
        expiring/expired KPIs.
        """
        stats = get_dashboard_stats()

        # ---- Fetch products ONCE ----
        try:
            products = get_all_products(include_archived=False)
        except Exception as e:
            print(f"[DashboardController] get_all_products failed: {e}")
            products = []

        total = len(products)
        # ---- Low stock: at or below threshold, INCLUDING 0 ----
        low = sum(
            1 for p in products
            if p.get("stock_qty", 0) <= (p.get("low_stock_level") or 0)
        )
        out = sum(1 for p in products if p.get("stock_qty", 0) <= 0)

        stats["total_products"]     = total
        stats["low_stock_count"]    = low
        stats["out_of_stock_count"] = out

        # ---- Batch aggregates ----
        try:
            stats["expiring_soon_count"] = count_expiring_soon(days=30)
        except Exception as e:
            print(f"[DashboardController] count_expiring_soon failed: {e}")
            stats["expiring_soon_count"] = 0

        try:
            stats["expired_count"] = count_expired()
        except Exception as e:
            print(f"[DashboardController] count_expired failed: {e}")
            stats["expired_count"] = 0

        return stats

    @staticmethod
    def low_stock_products(limit=500):
        try:
            products = get_all_products(include_archived=False)
        except Exception as e:
            print(f"[DashboardController] low_stock_products failed: {e}")
            return []

        rows = [
            p for p in products
            if p.get("stock_qty", 0) <= (p.get("low_stock_level") or 0)
        ]
        return rows[:limit]