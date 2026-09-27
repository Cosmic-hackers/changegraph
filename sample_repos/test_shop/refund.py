"""
refund.py — Refund processing for test_shop.

Handles customer return and refund requests.
Calls checkout.calculate_total to recalculate refund amounts
and payment.refund_payment to issue the financial refund.
Uses users.py for user validation.
"""

from typing import Optional
from users import get_user
from checkout import calculate_total, get_order
from payment import refund_payment, get_payment

# Simulated refund records
_REFUNDS: dict[int, dict] = {}
_REFUND_COUNTER = 0


def calculate_refund_amount(order_id: int, items_to_refund: list[dict]) -> float:
    """
    Calculate the refund amount for a subset of order items.

    Reuses checkout.calculate_total to ensure consistent pricing.
    Any modification to calculate_total directly affects refund amounts.

    items_to_refund: list of {product_id, quantity} dicts.
    """
    return calculate_total(items_to_refund)


def process_refund(
    user_id: int,
    order_id: int,
    payment_id: int,
    items_to_refund: list[dict],
) -> dict:
    """
    Process a full or partial refund for an order.

    Steps:
      1. Validate the user exists.
      2. Validate the order belongs to the user.
      3. Calculate refund amount via calculate_total.
      4. Issue the financial refund via payment.refund_payment.
      5. Record the refund.

    Returns a result dict with keys: success, refund_id, amount, error.
    """
    global _REFUND_COUNTER

    user = get_user(user_id)
    if user is None:
        return {"success": False, "refund_id": None, "amount": 0, "error": "User not found"}

    order = get_order(order_id)
    if order is None:
        return {"success": False, "refund_id": None, "amount": 0, "error": "Order not found"}

    if order["user_id"] != user_id:
        return {"success": False, "refund_id": None, "amount": 0, "error": "Order does not belong to user"}

    refund_amount = calculate_refund_amount(order_id, items_to_refund)

    payment_result = refund_payment(payment_id, refund_amount)
    if not payment_result["success"]:
        return {
            "success": False,
            "refund_id": None,
            "amount": refund_amount,
            "error": payment_result["error"],
        }

    _REFUND_COUNTER += 1
    refund_record = {
        "refund_id": _REFUND_COUNTER,
        "order_id": order_id,
        "user_id": user_id,
        "payment_id": payment_id,
        "items": items_to_refund,
        "amount": refund_amount,
        "status": "processed",
    }
    _REFUNDS[_REFUND_COUNTER] = refund_record
    return {
        "success": True,
        "refund_id": _REFUND_COUNTER,
        "amount": refund_amount,
        "error": None,
    }


def get_refund(refund_id: int) -> Optional[dict]:
    """Return a refund record by ID, or None if not found."""
    return _REFUNDS.get(refund_id)


def get_refunds_for_order(order_id: int) -> list[dict]:
    """Return all refunds associated with an order."""
    return [r for r in _REFUNDS.values() if r["order_id"] == order_id]


def get_refunds_for_user(user_id: int) -> list[dict]:
    """Return all refunds issued to a user."""
    return [r for r in _REFUNDS.values() if r["user_id"] == user_id]
