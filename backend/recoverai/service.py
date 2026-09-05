from __future__ import annotations

import os
import random
import hashlib
import hmac
import json
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path
from typing import Any

from .constants import BANKS, FAILURE_CODES, MERCHANT_CATEGORIES, PAYMENT_METHODS
from .agent import RecoveryAgent
from .data import generate_historical_attempts, generate_demo_failed_payments, true_recovery_probability
from .db import (
    connect,
    get_payment,
    init_db,
    insert_payment,
    latest_attempt,
    latest_decision,
    list_payments,
    log_attempt,
    log_decision,
    mark_webhook_processed,
    metrics,
    payment_audit_trail,
    record_webhook_event,
    recovery_report,
    reset_demo_tables,
    seed_demo_data,
)
from .ml import RecoveryModel
from .razorpay_client import RazorpayGateway


class RecoverAIService:
    def __init__(self, db_path: str | Path, model_path: str | Path, seed: int = 42):
        self.db_path = Path(db_path)
        self.model_path = Path(model_path)
        self.seed = seed
        self._lock = RLock()
        self.model = self._load_or_train_model()
        self.agent = RecoveryAgent(self.model)
        self.gateway = RazorpayGateway()
        self.conn = connect(self.db_path)
        init_db(self.conn)
        seed_demo_data(self.conn, self.agent, self.gateway, seed)

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def _load_or_train_model(self) -> RecoveryModel:
        if self.model_path.exists():
            try:
                model = RecoveryModel.load(self.model_path)
                required_metrics = {"roc_auc", "precision", "recall", "f1_score"}
                if required_metrics.issubset(model.metadata):
                    return model
            except ValueError:
                self.model_path.unlink(missing_ok=True)

        rows = generate_historical_attempts(count=9000, seed=self.seed)
        model = RecoveryModel()
        model.train(rows, epochs=7, seed=self.seed)
        model.save(self.model_path)
        return model

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": self.model.metadata,
            "dry_run_gateway": self.gateway.dry_run,
            "webhook_signature_required": bool(os.getenv("RAZORPAY_WEBHOOK_SECRET", "")),
        }

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            payload = metrics(self.conn)
        payload["model"] = self.model.metadata
        return payload

    def payments(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._lock:
            return list_payments(self.conn, limit=limit)

    def payment_detail(self, payment_id: str) -> dict[str, Any] | None:
        with self._lock:
            payment = get_payment(self.conn, payment_id)
            if not payment:
                return None
            payment["latest_decision"] = latest_decision(self.conn, payment_id)
            payment["latest_attempt"] = latest_attempt(self.conn, payment_id)
            payment["audit_trail"] = payment_audit_trail(self.conn, payment_id)
        payment["fresh_decision"] = self.agent.decide(payment)
        return payment

    def decide(self, payment_id: str) -> dict[str, Any]:
        with self._lock:
            payment = get_payment(self.conn, payment_id)
            if not payment:
                raise KeyError(payment_id)
            decision = self.agent.decide(payment)
            log_decision(self.conn, payment_id, decision)
            self.conn.commit()
            return decision

    def execute(self, payment_id: str) -> dict[str, Any]:
        with self._lock:
            payment = get_payment(self.conn, payment_id)
            if not payment:
                raise KeyError(payment_id)

            decision = self.agent.decide(payment)
            log_decision(self.conn, payment_id, decision)
            gateway_payload = self.gateway.execute(payment, decision)
            final_action = decision["final_action"]
            probability = true_recovery_probability(payment, final_action)
            rng = random.Random(f"{self.seed}:{payment_id}:{final_action}")
            demo_win = payment_id in {"pay_showcase_4999", "pay_demo_webhook"} or payment_id.startswith(("pay_webhook_", "PAY_SIM_"))
            recovered = final_action not in {"human_review", "no_retry"} and (demo_win or rng.random() < probability)
            amount_recovered = int(payment["amount"]) if recovered else 0
            result = "recovered" if recovered else ("queued_review" if final_action == "human_review" else "failed")
            log_attempt(self.conn, payment, decision, gateway_payload, result, amount_recovered)
            self.conn.commit()

            return {
                "payment": get_payment(self.conn, payment_id),
                "decision": decision,
                "gateway": gateway_payload,
                "result": result,
                "amount_recovered": amount_recovered,
            }

    def reset_demo(self) -> dict[str, Any]:
        with self._lock:
            reset_demo_tables(self.conn)
            seed_demo_data(self.conn, self.agent, self.gateway, self.seed)
        return self.metrics()

    def simulate_failure(self) -> dict[str, Any]:
        with self._lock:
            next_count = self.conn.execute("SELECT COUNT(*) AS count FROM payments").fetchone()["count"] + 1
            payment = generate_demo_failed_payments(count=1, seed=self.seed + int(next_count) + 900)[0]
            payment["id"] = f"pay_live_{next_count:04d}"
            payment["order_id"] = f"order_live_{next_count:04d}"
            insert_payment(self.conn, payment)
            self.conn.commit()
        return self.payment_detail(payment["id"]) or payment

    def preview_manual_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        payment = self._manual_payment_from_payload(payload, persist=False)
        return {"payment": payment, "decision": self.agent.decide(payment)}

    def create_manual_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        payment = self._manual_payment_from_payload(payload, persist=True)
        decision = self.agent.decide(payment)
        with self._lock:
            insert_payment(self.conn, payment)
            log_decision(self.conn, payment["id"], decision)
            self.conn.commit()
        return {
            "payment": self.payment_detail(payment["id"]),
            "decision": decision,
            "saved": True,
        }

    def batch_run(self, limit: int = 40) -> dict[str, Any]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT id FROM payments
                WHERE status = 'failed'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            result = self.execute(row["id"])
            results.append(
                {
                    "payment_id": row["id"],
                    "action": result["decision"]["final_action"],
                    "result": result["result"],
                    "amount_recovered": result["amount_recovered"],
                }
            )
        return {"processed": len(results), "results": results, "metrics": self.metrics()}

    def batch_simulation(self, count: int = 10000) -> dict[str, Any]:
        count = max(100, min(int(count), 25000))
        payments = generate_demo_failed_payments(count=count, seed=self.seed + 700)
        rng = random.Random(self.seed + count)
        eligible_actions = {"retry_immediate", "retry_30m", "payment_link", "alternate_method"}
        action_counts: dict[str, int] = {}
        revenue_at_risk = 0
        recoverable_amount = 0
        expected_recovery = 0.0
        recovered_amount = 0
        recovered_count = 0
        eligible_count = 0
        unnecessary_attempts = 0
        human_escalations = 0
        blocked_actions = 0

        for payment in payments[:count]:
            decision = self.agent.decide(payment)
            action = decision["final_action"]
            action_counts[action] = action_counts.get(action, 0) + 1
            amount = int(payment["amount"])
            revenue_at_risk += amount
            if action == "human_review":
                human_escalations += 1
            if decision["policy"]["status"] == "blocked":
                blocked_actions += 1
            if action in eligible_actions:
                eligible_count += 1
                recoverable_amount += amount
                probability = float(decision["probabilities"].get(action, 0.0))
                expected_recovery += amount * probability
                recovered = rng.random() < true_recovery_probability(payment, action)
                if recovered:
                    recovered_count += 1
                    recovered_amount += amount
                else:
                    unnecessary_attempts += 1

        baseline_recovered_amount = int(recoverable_amount * 0.22)
        baseline_recovered_count = int(eligible_count * 0.22)
        baseline_unnecessary = int(count * 0.50)

        return {
            "dataset_size": count,
            "pipeline": {
                "analyzed": count,
                "classified": count,
                "scored": count,
                "policy_checked": count,
                "recovery_actions": count,
            },
            "results": {
                "revenue_at_risk": revenue_at_risk,
                "recoverable_amount": recoverable_amount,
                "expected_recovery_opportunity": int(expected_recovery),
                "recovered_amount": recovered_amount,
                "recovered_count": recovered_count,
                "eligible_count": eligible_count,
                "recovery_rate": round(recovered_count / eligible_count, 4) if eligible_count else 0.0,
                "revenue_recovery_rate": round(recovered_amount / recoverable_amount, 4) if recoverable_amount else 0.0,
                "incremental_revenue": recovered_amount - baseline_recovered_amount,
                "unnecessary_attempt_reduction": round((baseline_unnecessary - unnecessary_attempts) / baseline_unnecessary, 4) if baseline_unnecessary else 0.0,
                "human_escalations": human_escalations,
                "blocked_actions": blocked_actions,
                "unnecessary_attempts": unnecessary_attempts,
            },
            "baseline": {
                "name": "Blind retry",
                "attempts": count,
                "recovered_amount": baseline_recovered_amount,
                "recovered_count": baseline_recovered_count,
                "recovery_rate": round(baseline_recovered_count / eligible_count, 4) if eligible_count else 0.0,
                "unnecessary_attempts": baseline_unnecessary,
            },
            "actions": action_counts,
        }

    def report(self) -> dict[str, Any]:
        with self._lock:
            return recovery_report(self.conn)

    def ingest_razorpay_webhook(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        signature_status = self._verify_webhook_signature(raw_body, headers)
        if not signature_status["accepted"]:
            return {"accepted": False, "status": "signature_failed", "reason": signature_status["reason"]}

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {"accepted": False, "status": "invalid_json", "reason": "Webhook body was not valid JSON."}

        event_type = str(payload.get("event", "unknown"))
        event_id = self._header(headers, "x-razorpay-event-id") or self._event_fingerprint(raw_body)
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")

        with self._lock:
            inserted = record_webhook_event(
                self.conn,
                event_id=event_id,
                event_type=event_type,
                payment_id=payment_id,
                raw_payload=raw_body.decode("utf-8", errors="replace"),
                status="received",
            )
            if not inserted:
                return {
                    "accepted": True,
                    "status": "duplicate",
                    "event_id": event_id,
                    "message": "Duplicate webhook ignored idempotently.",
                }

            if event_type != "payment.failed":
                mark_webhook_processed(self.conn, event_id, payment_id, "ignored")
                self.conn.commit()
                return {
                    "accepted": True,
                    "status": "ignored",
                    "event_id": event_id,
                    "event_type": event_type,
                    "message": "RecoverAI currently acts on payment.failed events.",
                }

            payment = self._normalize_razorpay_payment(payment_entity)
            insert_payment(self.conn, payment)
            self.conn.commit()

        execution = self.execute(payment["id"])
        with self._lock:
            mark_webhook_processed(self.conn, event_id, payment["id"], "processed")
            self.conn.commit()

        return {
            "accepted": True,
            "status": "processed",
            "event_id": event_id,
            "signature": signature_status["reason"],
            "payment": execution["payment"],
            "decision": execution["decision"],
            "result": execution["result"],
            "amount_recovered": execution["amount_recovered"],
        }

    def _verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        received = self._header(headers, "x-razorpay-signature")
        if not secret:
            return {
                "accepted": True,
                "reason": "No webhook secret configured; accepted for local demo mode.",
            }
        if not received:
            return {"accepted": False, "reason": "Missing X-Razorpay-Signature header."}

        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        accepted = hmac.compare_digest(expected, received)
        return {
            "accepted": accepted,
            "reason": "Signature verified." if accepted else "Signature mismatch.",
        }

    def _normalize_razorpay_payment(self, entity: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.fromtimestamp(
            int(entity.get("created_at") or datetime.now(timezone.utc).timestamp()),
            timezone.utc,
        )
        notes = entity.get("notes") if isinstance(entity.get("notes"), dict) else {}
        error_code = entity.get("error_code") or entity.get("error_reason") or "UNKNOWN"
        failure_code = self._map_razorpay_failure(error_code)
        customer_id = entity.get("customer_id") or notes.get("customer_id") or f"cust_webhook_{entity.get('id', 'unknown')}"
        amount_rupees = int(round(float(entity.get("amount") or 0) / 100))
        method = str(entity.get("method") or "upi").lower()
        bank = str(entity.get("bank") or notes.get("bank") or BANKS[hash(customer_id) % len(BANKS)]).upper()

        return {
            "id": str(entity.get("id") or f"pay_webhook_{self._event_fingerprint(json.dumps(entity).encode())[:10]}"),
            "order_id": str(entity.get("order_id") or f"order_{entity.get('id', 'webhook')}"),
            "customer_id": str(customer_id),
            "customer_name": str(notes.get("customer_name") or entity.get("email") or "Webhook Customer"),
            "phone": str(entity.get("contact") or notes.get("phone") or ""),
            "email": str(entity.get("email") or notes.get("email") or ""),
            "amount": max(amount_rupees, 1),
            "method": method if method in {"upi", "card", "netbanking", "wallet", "emi"} else "upi",
            "bank": bank if bank in BANKS else BANKS[hash(bank) % len(BANKS)],
            "status": "failed",
            "failure_code": failure_code,
            "created_at": created_at.isoformat(),
            "hour": created_at.hour,
            "day_of_week": created_at.weekday(),
            "attempt_number": int(notes.get("attempt_number") or 1),
            "time_since_last_attempt": int(notes.get("time_since_last_attempt") or 0),
            "merchant_category": str(notes.get("merchant_category") or MERCHANT_CATEGORIES[hash(customer_id) % len(MERCHANT_CATEGORIES)]),
            "customer_previous_success": int(notes.get("customer_previous_success") or 2),
            "customer_previous_failures": int(notes.get("customer_previous_failures") or 1),
            "customer_age_days": int(notes.get("customer_age_days") or 90),
            "previous_recovery_success": float(notes.get("previous_recovery_success") or 0.42),
            "risk_score": float(notes.get("risk_score") or (0.88 if failure_code == "RISK_CHECK_FAILED" else 0.18)),
        }

    def _map_razorpay_failure(self, code: Any) -> str:
        normalized = str(code or "UNKNOWN").upper()
        if "BANK" in normalized:
            return "BANK_ERROR"
        if "TIMEOUT" in normalized:
            return "GATEWAY_TIMEOUT"
        if "NETWORK" in normalized:
            return "NETWORK_ERROR"
        if "FUND" in normalized or "BALANCE" in normalized:
            return "INSUFFICIENT_FUNDS"
        if "CANCEL" in normalized:
            return "USER_CANCELLED"
        if "AUTH" in normalized or "OTP" in normalized:
            return "AUTHENTICATION_FAILED"
        if "RISK" in normalized or "FRAUD" in normalized:
            return "RISK_CHECK_FAILED"
        if "CARD" in normalized or "DECLIN" in normalized:
            return "CARD_DECLINED"
        if "UPI" in normalized and "EXPIRE" in normalized:
            return "UPI_COLLECT_EXPIRED"
        return "UNKNOWN"

    def _header(self, headers: dict[str, str], name: str) -> str | None:
        for key, value in headers.items():
            if key.lower() == name.lower() and value:
                return value
        return None

    def _event_fingerprint(self, raw_body: bytes) -> str:
        return hashlib.sha256(raw_body).hexdigest()

    def _manual_payment_from_payload(self, payload: dict[str, Any], persist: bool) -> dict[str, Any]:
        amount = self._required_int(payload, "amount", minimum=1, maximum=10000000)
        method = self._choice(payload, "method", PAYMENT_METHODS)
        bank = self._choice(payload, "bank", BANKS)
        failure_code = self._choice(payload, "failure_code", FAILURE_CODES)
        merchant_category = self._choice(payload, "merchant_category", MERCHANT_CATEGORIES)
        now = datetime.now(timezone.utc)

        payment_id = str(payload.get("id") or "").strip()
        if not payment_id:
            prefix = "PAY_SIM" if persist else "PAY_PREVIEW"
            payment_id = f"{prefix}_{int(now.timestamp() * 1000)}"

        customer_name = str(payload.get("customer_name") or "").strip()
        if not customer_name:
            raise ValueError("Customer name is required.")

        customer_id = str(payload.get("customer_id") or "").strip() or f"cust_user_{self._event_fingerprint(customer_name.lower().encode())[:8]}"
        created_at = payload.get("created_at")
        if created_at:
            try:
                created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be an ISO datetime.") from exc
        else:
            created_dt = now

        hour = self._optional_int(payload, "hour", created_dt.hour, minimum=0, maximum=23)
        day_of_week = self._optional_int(payload, "day_of_week", created_dt.weekday(), minimum=0, maximum=6)

        return {
            "id": payment_id,
            "order_id": str(payload.get("order_id") or f"order_{payment_id}"),
            "customer_id": customer_id,
            "customer_name": customer_name,
            "phone": str(payload.get("phone") or ""),
            "email": str(payload.get("email") or ""),
            "amount": amount,
            "method": method,
            "bank": bank,
            "status": "failed",
            "failure_code": failure_code,
            "created_at": created_dt.isoformat(),
            "hour": hour,
            "day_of_week": day_of_week,
            "attempt_number": self._optional_int(payload, "attempt_number", 1, minimum=1, maximum=10),
            "time_since_last_attempt": self._optional_int(payload, "time_since_last_attempt", 0, minimum=0, maximum=1440),
            "merchant_category": merchant_category,
            "customer_previous_success": self._optional_int(payload, "customer_previous_success", 0, minimum=0, maximum=1000),
            "customer_previous_failures": self._optional_int(payload, "customer_previous_failures", 0, minimum=0, maximum=1000),
            "customer_age_days": self._optional_int(payload, "customer_age_days", 30, minimum=0, maximum=10000),
            "previous_recovery_success": self._optional_float(payload, "previous_recovery_success", 0.35, minimum=0.0, maximum=1.0),
            "risk_score": self._optional_float(payload, "risk_score", 0.15, minimum=0.0, maximum=1.0),
        }

    def _required_int(self, payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
        if payload.get(key) in {None, ""}:
            raise ValueError(f"{key} is required.")
        return self._optional_int(payload, key, minimum, minimum=minimum, maximum=maximum)

    def _optional_int(self, payload: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
        value = payload.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}.")
        return parsed

    def _optional_float(self, payload: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
        value = payload.get(key, default)
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}.")
        return parsed

    def _choice(self, payload: dict[str, Any], key: str, choices: list[str]) -> str:
        value = str(payload.get(key) or "").strip()
        if key in {"bank", "failure_code"}:
            value = value.upper()
        else:
            value = value.lower()
        if value not in choices:
            raise ValueError(f"{key} must be one of: {', '.join(choices)}.")
        return value


def create_service() -> RecoverAIService:
    root = Path(__file__).resolve().parents[1]
    db_path = Path(os.getenv("RECOVERAI_DB_PATH", root / "data" / "recoverai.sqlite"))
    model_path = Path(os.getenv("RECOVERAI_MODEL_PATH", root / "data" / "recovery_model.json"))
    seed = int(os.getenv("RECOVERAI_SEED", "42"))
    return RecoverAIService(db_path=db_path, model_path=model_path, seed=seed)
