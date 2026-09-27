"""
checkout.py — Order checkout logic for test_shop.

Orchestrates the full checkout flow:
  1. Validates the user (users.py)
  2. Reads the cart (cart.py)
  3. Validates stock (products.py)
  4. Calculates the order total (calculate_total)
  5. Creates an order record
  6. Triggers payment (payment.py)
  7. Generates an invoice (invoice.py)
  8. Clears the cart on success

This module is the central hub of the business logic.
"""

from typing import Optional
from users import get_user, authenticate_user
from cart import get_cart, clear_cart
from products import get_product_price, check_stock, reduce_stock
from payment import process_payment
from invoice import generate_invoice

# Simulated in-memory order store
_ORDERS: dict[int, dict] = {}
_ORDER_COUNTER = 0


def calculate_total(cart_items: list[dict], discount_percent: float = 0.0) -> float:
    """
    Calculate the total price for a list of cart items.

    Each item must have 'product_id' and 'quantity' keys.
    Raises ValueError if a product is not found.

    Optional discount_percent (0-100) is applied to the final total.
    This is the core pricing function. Any change here directly
    affects invoice generation, refund calculations, and payment amounts.
    """
    total = 0.0
    for item in cart_items:
        price = get_product_price(item["product_id"])
        if price is None:
            raise ValueError(f"Product {item['product_id']} not found")
        total += price * item["quantity"]
    if discount_percent > 0.0:
        total = total * (1 - discount_percent / 100)
    return round(total, 2)


def apply_discount(total: float, discount_code: Optional[str]) -> float:
    """
    Apply a discount code to a total.

    Known codes:
      SAVE10 - 10% off
      SAVE20 - 20% off
      SAVE30 - 30% off (new)

    Returns the discounted total (or the original total if code is invalid).
    """
    discounts = {"SAVE10": 0.10, "SAVE20": 0.20, "SAVE30": 0.30}
    if discount_code and discount_code in discounts:
        return round(total * (1 - discounts[discount_code]), 2)
    return total


def validate_cart(cart_items: list[dict]) -> list[str]:
    """
    Check that all cart items have sufficient stock.

    Returns a list of error strings (empty list means the cart is valid).
    """
    errors = []
    for item in cart_items:
        if not check_stock(item["product_id"], item["quantity"]):
            errors.append(f"Insufficient stock for product {item['product_id']}")
    return errors


def create_order(user_id: int, cart_items: list[dict], total: float) -> dict:
    """
    Persist a new order record and return it.

    Called internally by checkout() after payment succeeds.
    """
    global _ORDER_COUNTER
    _ORDER_COUNTER += 1
    order = {
        "order_id": _ORDER_COUNTER,
        "user_id": user_id,
        "items": cart_items,
        "total": total,
        "status": "confirmed",
    }
    _ORDERS[_ORDER_COUNTER] = order
    return order


def get_order(order_id: int) -> Optional[dict]:
    """Return an order record by ID, or None if not found."""
    return _ORDERS.get(order_id)


def checkout(user_id: int, token: str, discount_code: Optional[str] = None) -> dict:
    """
    Execute the full checkout flow for a user.

    Steps:
      1. Authenticate the user.
      2. Load the cart.
      3. Validate stock.
      4. Calculate total.
      5. Apply discount.
      6. Process payment.
      7. Reduce stock.
      8. Create order.
      9. Generate invoice.
      10. Clear cart.

    Returns a result dict with keys: success, order, invoice, error.
    """
    if not authenticate_user(user_id, token):
        return {"success": False, "error": "Authentication failed"}

    cart_items = get_cart(user_id)
    if not cart_items:
        return {"success": False, "error": "Cart is empty"}

    stock_errors = validate_cart(cart_items)
    if stock_errors:
        return {"success": False, "error": stock_errors}

    total = calculate_total(cart_items)
    total = apply_discount(total, discount_code)

    payment_result = process_payment(user_id, total)
    if not payment_result["success"]:
        return {"success": False, "error": payment_result["error"]}

    for item in cart_items:
        reduce_stock(item["product_id"], item["quantity"])

    order = create_order(user_id, cart_items, total)
    invoice = generate_invoice(order)
    clear_cart(user_id)

    return {"success": True, "order": order, "invoice": invoice}
