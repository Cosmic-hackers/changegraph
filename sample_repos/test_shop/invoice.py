"""
invoice.py — Invoice generation for test_shop.

Generates invoice documents from completed orders.
Called by checkout.py after a successful payment.
Calls checkout.calculate_total indirectly via the order's stored total.
Uses user info from users.py for billing details.
"""

from typing import Optional
from users import get_user

# Simulated invoice store: {invoice_id: dict}
_INVOICES: dict[int, dict] = {}
_INVOICE_COUNTER = 0


def generate_invoice(order: dict) -> dict:
    """
    Generate an invoice for a completed order.

    Expects an order dict with keys: order_id, user_id, items, total.
    Returns the created invoice dict.

    This function is directly downstream of checkout.calculate_total
    because the order total it receives was computed by calculate_total().
    Any change to pricing logic in checkout.py will be reflected here.
    """
    global _INVOICE_COUNTER

    user = get_user(order["user_id"])
    billing_name = user["name"] if user else "Unknown"
    billing_email = user["email"] if user else ""

    _INVOICE_COUNTER += 1
    invoice = {
        "invoice_id": _INVOICE_COUNTER,
        "order_id": order["order_id"],
        "user_id": order["user_id"],
        "billing_name": billing_name,
        "billing_email": billing_email,
        "line_items": order["items"],
        "total": order["total"],
        "status": "issued",
    }
    _INVOICES[_INVOICE_COUNTER] = invoice
    return invoice


def get_invoice(invoice_id: int) -> Optional[dict]:
    """Return an invoice by ID, or None if not found."""
    return _INVOICES.get(invoice_id)


def get_invoices_for_order(order_id: int) -> list[dict]:
    """Return all invoices associated with an order."""
    return [inv for inv in _INVOICES.values() if inv["order_id"] == order_id]


def get_invoices_for_user(user_id: int) -> list[dict]:
    """Return all invoices for a user."""
    return [inv for inv in _INVOICES.values() if inv["user_id"] == user_id]


def recalculate_invoice_total(invoice_id: int, new_total: float) -> bool:
    """
    Update the total on an existing invoice (e.g., after a discount correction).

    Returns True on success, False if the invoice was not found.
    This function is sensitive to changes in checkout.calculate_total logic.
    """
    invoice = _INVOICES.get(invoice_id)
    if invoice is None:
        return False
    invoice["total"] = new_total
    return True
