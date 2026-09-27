"""
payment.py — Payment processing for test_shop.

Handles payment authorization and recording.
Called by checkout.py after order total is calculated.
Calls users.py to look up user payment details.
"""

from typing import Optional
from users import get_user

# Simulated payment records: {payment_id: dict}
_PAYMENTS: dict[int, dict] = {}
_PAYMENT_COUNTER = 0

# Simulated blocked users (e.g., failed fraud check)
_BLOCKED_USERS: set[int] = set()


def process_payment(user_id: int, amount: float) -> dict:
    """
    Authorize and record a payment for the given user and amount.

    Returns a result dict with keys: success, payment_id, error.
    Called by checkout.py as part of the checkout flow.
    """
    global _PAYMENT_COUNTER

    user = get_user(user_id)
    if user is None:
        return {"success": False, "payment_id": None, "error": "User not found"}

    if user_id in _BLOCKED_USERS:
        return {"success": False, "payment_id": None, "error": "Payment blocked"}

    if amount <= 0:
        return {"success": False, "payment_id": None, "error": "Invalid amount"}

    _PAYMENT_COUNTER += 1
    payment = {
        "payment_id": _PAYMENT_COUNTER,
        "user_id": user_id,
        "amount": amount,
        "status": "authorized",
    }
    _PAYMENTS[_PAYMENT_COUNTER] = payment
    return {"success": True, "payment_id": _PAYMENT_COUNTER, "error": None}


def refund_payment(payment_id: int, amount: float) -> dict:
    """
    Issue a partial or full refund for a previously authorized payment.

    Returns a result dict with keys: success, refund_id, error.
    Called by refund.py when processing a return request.
    """
    global _PAYMENT_COUNTER

    payment = _PAYMENTS.get(payment_id)
    if payment is None:
        return {"success": False, "refund_id": None, "error": "Payment not found"}

    if amount > payment["amount"]:
        return {"success": False, "refund_id": None, "error": "Refund exceeds original amount"}

    _PAYMENT_COUNTER += 1
    refund_record = {
        "payment_id": _PAYMENT_COUNTER,
        "original_payment_id": payment_id,
        "user_id": payment["user_id"],
        "amount": amount,
        "status": "refunded",
    }
    _PAYMENTS[_PAYMENT_COUNTER] = refund_record
    return {"success": True, "refund_id": _PAYMENT_COUNTER, "error": None}


def get_payment(payment_id: int) -> Optional[dict]:
    """Return a payment record by ID, or None if not found."""
    return _PAYMENTS.get(payment_id)


def get_user_payments(user_id: int) -> list[dict]:
    """Return all payment records for a user."""
    return [p for p in _PAYMENTS.values() if p["user_id"] == user_id]


def block_user_payments(user_id: int) -> None:
    """Block a user from making future payments (fraud/admin action)."""
    _BLOCKED_USERS.add(user_id)


def unblock_user_payments(user_id: int) -> None:
    """Unblock a previously blocked user."""
    _BLOCKED_USERS.discard(user_id)
