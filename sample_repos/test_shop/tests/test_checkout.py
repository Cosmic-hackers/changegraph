"""
tests/test_checkout.py — Tests for checkout.py

Covers calculate_total, apply_discount, validate_cart, and checkout flow.
"""

import sys
import os

# Allow importing from parent directory (test_shop root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checkout import calculate_total, apply_discount, validate_cart, checkout


def test_calculate_total_single_item():
    items = [{"product_id": 101, "quantity": 2}]
    total = calculate_total(items)
    assert total == round(9.99 * 2, 2), f"Expected {round(9.99 * 2, 2)}, got {total}"


def test_calculate_total_multiple_items():
    items = [
        {"product_id": 101, "quantity": 1},
        {"product_id": 102, "quantity": 1},
    ]
    total = calculate_total(items)
    assert total == round(9.99 + 24.99, 2)


def test_calculate_total_empty_cart():
    total = calculate_total([])
    assert total == 0.0


def test_apply_discount_save10():
    total = apply_discount(100.0, "SAVE10")
    assert total == 90.0


def test_apply_discount_save20():
    total = apply_discount(100.0, "SAVE20")
    assert total == 80.0


def test_apply_discount_invalid_code():
    total = apply_discount(100.0, "INVALID")
    assert total == 100.0


def test_apply_discount_no_code():
    total = apply_discount(50.0, None)
    assert total == 50.0


def test_validate_cart_sufficient_stock():
    items = [{"product_id": 101, "quantity": 1}]
    errors = validate_cart(items)
    assert errors == []


def test_validate_cart_insufficient_stock():
    # Product 104 has only 10 in stock
    items = [{"product_id": 104, "quantity": 999}]
    errors = validate_cart(items)
    assert len(errors) == 1
    assert "104" in errors[0]


def test_checkout_empty_cart_returns_error():
    result = checkout(user_id=1, token="valid-token")
    # Cart is empty at start of test — should fail
    assert not result["success"]
    assert "Cart is empty" in result["error"] or "empty" in result["error"].lower()


def test_checkout_invalid_auth():
    result = checkout(user_id=999, token="")
    assert not result["success"]


if __name__ == "__main__":
    test_calculate_total_single_item()
    test_calculate_total_multiple_items()
    test_calculate_total_empty_cart()
    test_apply_discount_save10()
    test_apply_discount_save20()
    test_apply_discount_invalid_code()
    test_apply_discount_no_code()
    test_validate_cart_sufficient_stock()
    test_validate_cart_insufficient_stock()
    test_checkout_empty_cart_returns_error()
    test_checkout_invalid_auth()
    print("All checkout tests passed.")
