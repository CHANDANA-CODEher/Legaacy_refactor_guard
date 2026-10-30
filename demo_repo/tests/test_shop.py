"""Tests for demo_repo/shop.py legacy business calculation."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure demo_repo directory is importable whether tests run from
# repository root or workspace root.
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from shop import calculate_order_total


class TestCalculateOrderTotal:
    """Test suite verifying existing behavior of legacy shopping cart calculations."""

    def test_empty_cart_returns_zero(self) -> None:
        assert calculate_order_total([]) == 0.0
        assert calculate_order_total(None) == 0.0

    def test_standard_customer_under_free_shipping_threshold(self) -> None:
        # 2 items @ $10.00 = $20.00 subtotal
        # Shipping = $5.00 (under $50)
        # Tax = 8% of $20.00 = $1.60
        # Total = $20.00 + $1.60 + $5.00 = $26.60
        items = [{"price": 10.0, "quantity": 2}]
        total = calculate_order_total(items, customer_type="standard")
        assert total == 26.60

    def test_standard_customer_over_free_shipping_threshold(self) -> None:
        # 2 items @ $30.00 = $60.00 subtotal
        # Shipping = $0.00 (>= $50)
        # Tax = 8% of $60.00 = $4.80
        # Total = $60.00 + $4.80 + $0.00 = $64.80
        items = [{"price": 30.0, "quantity": 2}]
        total = calculate_order_total(items, customer_type="standard")
        assert total == 64.80

    def test_premium_customer_membership_discount(self) -> None:
        # 2 items @ $30.00 = $60.00 subtotal
        # Premium discount (10%) = $6.00 -> $54.00
        # Shipping = $0.00 ($54.00 >= $50)
        # Tax = 8% of $54.00 = $4.32
        # Total = $54.00 + $4.32 + $0.00 = $58.32
        items = [{"price": 30.0, "quantity": 2}]
        total = calculate_order_total(items, customer_type="premium")
        assert total == 58.32

    def test_vip_customer_membership_discount(self) -> None:
        # 2 items @ $50.00 = $100.00 subtotal
        # VIP discount (20%) = $20.00 -> $80.00
        # Shipping = $0.00 ($80.00 >= $50)
        # Tax = 8% of $80.00 = $6.40
        # Total = $80.00 + $6.40 + $0.00 = $86.40
        items = [{"price": 50.0, "quantity": 2}]
        total = calculate_order_total(items, customer_type="vip")
        assert total == 86.40

    def test_save10_coupon_code_applied(self) -> None:
        # 1 item @ $50.00 = $50.00 subtotal
        # SAVE10 coupon = -$10.00 -> $40.00
        # Shipping = $5.00 ($40.00 < $50)
        # Tax = 8% of $40.00 = $3.20
        # Total = $40.00 + $3.20 + $5.00 = $48.20
        items = [{"price": 50.0, "quantity": 1}]
        total = calculate_order_total(items, customer_type="standard", coupon_code="SAVE10")
        assert total == 48.20

    def test_freeship_coupon_code_applied(self) -> None:
        # 1 item @ $20.00 = $20.00 subtotal
        # FREESHIP coupon = $0.00 shipping
        # Tax = 8% of $20.00 = $1.60
        # Total = $20.00 + $1.60 + $0.00 = $21.60
        items = [{"price": 20.0, "quantity": 1}]
        total = calculate_order_total(items, customer_type="standard", coupon_code="FREESHIP")
        assert total == 21.60

    def test_combined_vip_and_save10_coupon(self) -> None:
        # 2 items @ $50.00 = $100.00 subtotal
        # VIP discount (20%) = $20.00 -> $80.00
        # SAVE10 coupon = -$10.00 -> $70.00
        # Shipping = $0.00 ($70.00 >= $50)
        # Tax = 8% of $70.00 = $5.60
        # Total = $70.00 + $5.60 + $0.00 = $75.60
        items = [{"price": 50.0, "quantity": 2}]
        total = calculate_order_total(items, customer_type="vip", coupon_code="SAVE10")
        assert total == 75.60
