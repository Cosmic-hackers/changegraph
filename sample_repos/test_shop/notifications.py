"""
notifications.py — Notification dispatch for test_shop.

Sends email/SMS notifications for order and refund events.
Called by checkout.py and refund.py to notify users.
Calls users.py to look up contact information.
"""

from users import get_user


def send_order_confirmation(user_id: int, order: dict) -> bool:
    """
    Send an order confirmation notification to the user.

    Called by checkout.checkout() after a successful order is created.
    Returns True if the notification was dispatched successfully.
    """
    user = get_user(user_id)
    if user is None:
        return False
    # In production this would call an email/SMS gateway.
    print(
        f"[NOTIFY] Order #{order['order_id']} confirmed for {user['email']} "
        f"— total ${order['total']}"
    )
    return True


def send_refund_notification(user_id: int, refund: dict) -> bool:
    """
    Send a refund confirmation notification to the user.

    Called by refund.process_refund() after a refund is processed.
    Returns True if the notification was dispatched successfully.
    """
    user = get_user(user_id)
    if user is None:
        return False
    print(
        f"[NOTIFY] Refund #{refund['refund_id']} of ${refund['amount']} "
        f"issued to {user['email']}"
    )
    return True


def send_payment_failed_notification(user_id: int, reason: str) -> bool:
    """
    Notify the user that their payment failed.

    Called by checkout.py when process_payment returns failure.
    """
    user = get_user(user_id)
    if user is None:
        return False
    print(f"[NOTIFY] Payment failed for {user['email']}: {reason}")
    return True


def send_stock_alert(product_id: int, remaining_stock: int) -> None:
    """
    Send an internal stock-level alert to the admin.

    Called by checkout.py after reduce_stock when stock falls below threshold.
    """
    print(f"[ALERT] Product {product_id} low stock: {remaining_stock} remaining")
