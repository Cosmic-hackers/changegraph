"""
cart.py — Shopping cart management for test_shop.

Manages per-user cart state: add, remove, and retrieve items.
Called by checkout.py to build the order line items.
Calls products.py to validate product existence and stock.
"""

from typing import Optional
from products import get_product, check_stock

# Simulated in-memory cart store: {user_id: [{product_id, quantity}]}
_CARTS: dict[int, list[dict]] = {}


def get_cart(user_id: int) -> list[dict]:
    """Return the current cart for a user (empty list if none)."""
    return _CARTS.get(user_id, [])


def add_to_cart(user_id: int, product_id: int, quantity: int) -> bool:
    """
    Add a product to the user's cart.

    Returns False if the product does not exist or stock is insufficient.
    """
    if not check_stock(product_id, quantity):
        return False
    product = get_product(product_id)
    if product is None:
        return False

    cart = _CARTS.setdefault(user_id, [])
    for item in cart:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            return True
    cart.append({"product_id": product_id, "quantity": quantity})
    return True


def remove_from_cart(user_id: int, product_id: int) -> bool:
    """
    Remove all quantities of a product from the user's cart.

    Returns True if the item was found and removed, False otherwise.
    """
    cart = _CARTS.get(user_id, [])
    original_length = len(cart)
    _CARTS[user_id] = [item for item in cart if item["product_id"] != product_id]
    return len(_CARTS[user_id]) < original_length


def clear_cart(user_id: int) -> None:
    """Remove all items from a user's cart (called after successful checkout)."""
    _CARTS[user_id] = []


def get_cart_item_count(user_id: int) -> int:
    """Return the total number of distinct products in the user's cart."""
    return len(get_cart(user_id))


def cart_has_product(user_id: int, product_id: int) -> bool:
    """Return True if the product is already in the user's cart."""
    return any(item["product_id"] == product_id for item in get_cart(user_id))
