import json
import hmac
import hashlib
import requests
from typing import Optional

# =========================
# CONFIG
# =========================

MERITPAY_URL = "https://meritpay.hostir.in/api/v1/intent"

CLIENT_ID = os.getenv("MP_CLIENT")
CLIENT_SECRET = os.getenv("MP_SECRET")
WEBHOOK_SECRET = os.getenv("MP_WH_SECRET")

CURRENCY = "INR"


# =========================
# MAIN ORDER CREATION
# =========================

def create_order(
    amount_rupees: float,
    return_url: str,
    customer_name: str = "",
    notes: Optional[dict] = None
) -> dict:
    """
    Creates a Meritpay payment order.

    Returns:
    {
        "success": True,
        "order_id": "...",
        "invoice_id": "...",
        "payment_url": "..."
    }

    OR

    {
        "success": False,
        "error": "..."
    }
    """

    try:
        payload = {
            "clientId": CLIENT_ID,
            "clientSecret": CLIENT_SECRET,
            "amount": int(amount_rupees * 100),  # INR subunits
            "currency": CURRENCY,
            "returnUrl": return_url
        }

        if customer_name:
            payload["name"] = customer_name

        if notes:
            payload["notes"] = notes

        response = requests.post(
            MERITPAY_URL,
            json=payload,
            timeout=30
        )

        if response.status_code != 201:
            return {
                "success": False,
                "error": f"Gateway returned {response.status_code}"
            }

        data = response.json()["data"]

        return {
            "success": True,
            "order_id": data["orderId"],
            "invoice_id": data["invoiceId"],
            "payment_url": data["redirectUrl"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# =========================
# WEBHOOK SIGNATURE VERIFY
# =========================

def verify_webhook_signature(
    raw_body: bytes,
    received_signature: str
) -> bool:
    """
    Verifies X-Meritpay-Signature
    """

    generated_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(
        generated_signature,
        received_signature
    )


# =========================
# WEBHOOK PROCESSOR
# =========================

def process_webhook(
    raw_body: bytes,
    signature: str
) -> dict:
    """
    Call this from Flask/FastAPI webhook route.
    """

    if not verify_webhook_signature(
        raw_body,
        signature
    ):
        return {
            "success": False,
            "reason": "invalid_signature"
        }

    payload = json.loads(raw_body.decode())

    event = payload.get("event")

    if event == "payment.captured":

        entity = payload["payload"]["payment"]["entity"]

        return {
            "success": True,
            "status": "paid",
            "payment_id": entity["id"],
            "amount": entity["amount"],
            "order_id": entity["order_id"],
            "invoice_id": entity.get("invoice_id"),
            "method": entity["method"]
        }

    elif event == "payment.failed":

        entity = payload["payload"]["payment"]["entity"]

        return {
            "success": True,
            "status": "failed",
            "payment_id": entity["id"],
            "error": entity.get("error_description")
        }

    return {
        "success": True,
        "status": "ignored"
    }
