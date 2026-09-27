"""
tests/test_refund.py — Tests for refund.py

Covers calculate_refund_amount and process_refund.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import payment as pay_module
import checkout as co_module
import refund as ref_module


def _reset_all():
    """Reset all in-memory stores for a clean test run."""
    pay_module._PAYMENTS.clear()
    pay_module._PAYMENT_COUNTER = 0
    pay_module._BLOCKED_USERS.clear()

    co_module._ORDERS.clear()
    co_module._ORDER_COUNTER = 0

    ref_module._REFUNDS.clear()
    ref_module._REFUND_COUNTER = 0


def _create_paid_order(user_id: int = 1) -> dict:
    """Helper: create an order + payment and return (order, payment_id)."""
    from checkout import create_order
    from payment import process_payment

    items = [{"product_id": 101, "quantity": 1}]
    total = 9.99
    order = create_order(user_id, items, total)
    pay_result = process_payment(user_id, total)
    return order, pay_result["payment_id"]


def test_calculate_refund_amount():
    _reset_all()
    items = [{"product_id": 101, "quantity": 1}]
    amount = ref_module.calculate_refund_amount(order_id=1, items_to_refund=items)
    assert amount == 9.99


def test_process_refund_success():
    _reset_all()
    order, payment_id = _create_paid_order(user_id=1)
    result = ref_module.process_refund(
        user_id=1,
        order_id=order["order_id"],
        payment_id=payment_id,
        items_to_refund=[{"product_id": 101, "quantity": 1}],
    )
    assert result["success"] is True
    assert result["amount"] == 9.99
    assert result["refund_id"] is not None


def test_process_refund_unknown_user():
    _reset_all()
    order, payment_id = _create_paid_order(user_id=1)
    result = ref_module.process_refund(
        user_id=9999,
        order_id=order["order_id"],
        payment_id=payment_id,
        items_to_refund=[{"product_id": 101, "quantity": 1}],
    )
    assert result["success"] is False
    assert "User not found" in result["error"]


def test_process_refund_wrong_user():
    _reset_all()
    order, payment_id = _create_paid_order(user_id=1)
    result = ref_module.process_refund(
        user_id=2,  # different user
        order_id=order["order_id"],
        payment_id=payment_id,
        items_to_refund=[{"product_id": 101, "quantity": 1}],
    )
    assert result["success"] is False
    assert "belong" in result["error"].lower()


def test_process_refund_nonexistent_order():
    _reset_all()
    result = ref_module.process_refund(
        user_id=1,
        order_id=99999,
        payment_id=1,
        items_to_refund=[{"product_id": 101, "quantity": 1}],
    )
    assert result["success"] is False
    assert "Order not found" in result["error"]


if __name__ == "__main__":
    test_calculate_refund_amount()
    test_process_refund_success()
    test_process_refund_unknown_user()
    test_process_refund_wrong_user()
    test_process_refund_nonexistent_order()
    print("All refund tests passed.")
