"""
products.py — Product catalog management for test_shop.

Provides product lookup and inventory management.
Called by cart.py and checkout.py to fetch prices and validate stock.
"""

from typing import Optional


# Simulated in-memory product catalog
_PRODUCTS: dict[int, dict] = {
    101: {"id": 101, "name": "Widget A",   "price": 9.99,  "stock": 50},
    102: {"id": 102, "name": "Gadget B",   "price": 24.99, "stock": 30},
    103: {"id": 103, "name": "Doohickey C","price": 4.99,  "stock": 100},
    104: {"id": 104, "name": "Thingamajig","price": 49.99, "stock": 10},
}


def get_product(product_id: int) -> Optional[dict]:
    """Return a product record by ID, or None if not found."""
    return _PRODUCTS.get(product_id)


def get_product_price(product_id: int) -> Optional[float]:
    """Return the unit price of a product, or None if not found."""
    product = get_product(product_id)
    if product is None:
        return None
    return product["price"]


def check_stock(product_id: int, quantity: int) -> bool:
    """Return True if the requested quantity is available in stock."""
    product = get_product(product_id)
    if product is None:
        return False
    return product["stock"] >= quantity


def reduce_stock(product_id: int, quantity: int) -> bool:
    """
    Deduct quantity from stock.  Returns True on success, False if
    insufficient stock or product not found.
    Called by checkout.py after a successful order is placed.
    """
    if not check_stock(product_id, quantity):
        return False
    _PRODUCTS[product_id]["stock"] -= quantity
    return True


def list_products() -> list[dict]:
    """Return all products in the catalog."""
    return list(_PRODUCTS.values())
