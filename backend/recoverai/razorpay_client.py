from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


class RazorpayGateway:
    """Safe gateway boundary used by the policy-approved recovery executor."""

    def __init__(self) -> None:
        self.key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.dry_run = os.getenv("RECOVERAI_RAZORPAY_DRY_RUN", "true").lower() != "false"

    def execute(self, payment: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
        action = decision["final_action"]
        if action == "retry_immediate":
            return self._retry(payment, delay_minutes=0)
        if action == "retry_30m":
            return self._retry(payment, delay_minutes=30)
        if action == "payment_link":
            return self._payment_link(payment, decision)
        if action == "alternate_method":
            return self._alternate_method(payment, decision)
        if action == "human_review":
            return self._human_review(payment, decision)
        return self._no_retry(payment)

    def _retry(self, payment: dict[str, Any], delay_minutes: int) -> dict[str, Any]:
        execute_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        return {
            "gateway": "razorpay_test_simulator",
            "dry_run": self.dry_run,
            "operation": "retry_payment",
            "gateway_reference": f"retry_{secrets.token_hex(5)}",
            "execute_at": execute_at.isoformat(),
            "message": "Retry scheduled safely." if delay_minutes else "Immediate retry triggered safely.",
        }

    def _payment_link(self, payment: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
        reference = f"plink_{secrets.token_hex(6)}"
        return {
            "gateway": "razorpay_test_simulator",
            "dry_run": self.dry_run,
            "operation": "create_payment_link",
            "gateway_reference": reference,
            "payment_link": f"https://rzp.io/i/{reference}",
            "message": decision["customer_message"]["english"],
        }

    def _alternate_method(self, payment: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
        reference = f"alt_{secrets.token_hex(6)}"
        return {
            "gateway": "razorpay_test_simulator",
            "dry_run": self.dry_run,
            "operation": "send_alternate_method_checkout",
            "gateway_reference": reference,
            "payment_link": f"https://rzp.io/i/{reference}",
            "message": decision["customer_message"]["hinglish"],
        }

    def _human_review(self, payment: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
        return {
            "gateway": "internal_review_queue",
            "dry_run": True,
            "operation": "create_review_case",
            "gateway_reference": f"review_{secrets.token_hex(5)}",
            "message": "Payment routed to human review. No Razorpay money-moving call executed.",
        }

    def _no_retry(self, payment: dict[str, Any]) -> dict[str, Any]:
        return {
            "gateway": "recoverai_policy",
            "dry_run": True,
            "operation": "no_retry",
            "gateway_reference": f"skip_{secrets.token_hex(5)}",
            "message": "Recovery attempt skipped to avoid waste.",
        }

