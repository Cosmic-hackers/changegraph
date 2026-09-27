"""
tests/test_payment.py — Tests for payment.py

Covers process_payment, refund_payment, and user-blocking logic.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment import (
    process_payment,
    refund_payment,
    get_payment,
    block_user_payments,
    unblock_user_payments,
    _PAYMENTS,
)


def _reset():
    """Clear payment state between tests."""
    _PAYMENTS.clear()
    import payment as p
    p._PAYMENT_COUNTER = 0
    p._BLOCKED_USERS.clear()


def test_process_payment_success():
    _reset()
    result = process_payment(user_id=1, amount=50.0)
    assert result["success"] is True
    assert result["payment_id"] is not None
    assert result["error"] is None


def test_process_payment_unknown_user():
    _reset()
    result = process_payment(user_id=9999, amount=50.0)
    assert result["success"] is False
    assert "User not found" in result["error"]


def test_process_payment_zero_amount():
    _reset()
    result = process_payment(user_id=1, amount=0)
    assert result["success"] is False
    assert "Invalid amount" in result["error"]


def test_process_payment_blocked_user():
    _reset()
    block_user_payments(1)
    result = process_payment(user_id=1, amount=25.0)
    assert result["success"] is False
    assert "blocked" in result["error"].lower()
    unblock_user_payments(1)


def test_refund_payment_success():
    _reset()
    pay_result = process_payment(user_id=2, amount=100.0)
    refund_result = refund_payment(pay_result["payment_id"], 40.0)
    assert refund_result["success"] is True
    assert refund_result["refund_id"] is not None


def test_refund_payment_exceeds_original():
    _reset()
    pay_result = process_payment(user_id=2, amount=30.0)
    refund_result = refund_payment(pay_result["payment_id"], 50.0)
    assert refund_result["success"] is False
    assert "exceeds" in refund_result["error"].lower()


def test_refund_payment_not_found():
    _reset()
    result = refund_payment(9999, 10.0)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


if __name__ == "__main__":
    test_process_payment_success()
    test_process_payment_unknown_user()
    test_process_payment_zero_amount()
    test_process_payment_blocked_user()
    test_refund_payment_success()
    test_refund_payment_exceeds_original()
    test_refund_payment_not_found()
    print("All payment tests passed.")
