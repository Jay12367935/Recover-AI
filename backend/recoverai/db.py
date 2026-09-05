from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ACTIONS
from .data import generate_demo_failed_payments, true_recovery_probability


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    customer_previous_success INTEGER NOT NULL,
    customer_previous_failures INTEGER NOT NULL,
    customer_age_days INTEGER NOT NULL,
    previous_recovery_success REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    method TEXT NOT NULL,
    bank TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    hour INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    time_since_last_attempt INTEGER NOT NULL,
    merchant_category TEXT NOT NULL,
    risk_score REAL NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS recovery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id TEXT NOT NULL,
    action TEXT NOT NULL,
    probability REAL NOT NULL,
    expected_value REAL NOT NULL,
    executed_at TEXT NOT NULL,
    result TEXT NOT NULL,
    amount_recovered INTEGER NOT NULL,
    gateway_payload TEXT NOT NULL,
    customer_message TEXT NOT NULL,
    FOREIGN KEY(payment_id) REFERENCES payments(id)
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    final_action TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    policy_status TEXT NOT NULL,
    probabilities_json TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(payment_id) REFERENCES payments(id)
);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payment_id TEXT,
    received_at TEXT NOT NULL,
    processed_at TEXT,
    status TEXT NOT NULL,
    raw_payload TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def reset_demo_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM recovery_attempts")
    conn.execute("DELETE FROM agent_logs")
    conn.execute("DELETE FROM webhook_events")
    conn.execute("DELETE FROM payments")
    conn.execute("DELETE FROM customers")
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def payment_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payment = row_to_dict(row) or {}
    payment.update(
        {
            "customer_name": row["name"],
            "phone": row["phone"],
            "email": row["email"],
            "customer_previous_success": row["customer_previous_success"],
            "customer_previous_failures": row["customer_previous_failures"],
            "customer_age_days": row["customer_age_days"],
            "previous_recovery_success": row["previous_recovery_success"],
        }
    )
    return payment


def get_payment(conn: sqlite3.Connection, payment_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.*, c.name, c.phone, c.email, c.customer_previous_success,
               c.customer_previous_failures, c.customer_age_days, c.previous_recovery_success
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        WHERE p.id = ?
        """,
        (payment_id,),
    ).fetchone()
    return payment_from_row(row) if row else None


def upsert_customer(conn: sqlite3.Connection, payment: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO customers (
            id, name, phone, email, customer_previous_success, customer_previous_failures,
            customer_age_days, previous_recovery_success
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            phone=excluded.phone,
            email=excluded.email,
            customer_previous_success=excluded.customer_previous_success,
            customer_previous_failures=excluded.customer_previous_failures,
            customer_age_days=excluded.customer_age_days,
            previous_recovery_success=excluded.previous_recovery_success
        """,
        (
            payment["customer_id"],
            payment.get("customer_name", "Customer"),
            payment.get("phone", ""),
            payment.get("email", ""),
            int(payment.get("customer_previous_success", 0)),
            int(payment.get("customer_previous_failures", 0)),
            int(payment.get("customer_age_days", 0)),
            float(payment.get("previous_recovery_success", 0.0)),
        ),
    )


def insert_payment(conn: sqlite3.Connection, payment: dict[str, Any]) -> None:
    upsert_customer(conn, payment)
    conn.execute(
        """
        INSERT OR REPLACE INTO payments (
            id, order_id, customer_id, amount, method, bank, status, failure_code,
            created_at, hour, day_of_week, attempt_number, time_since_last_attempt,
            merchant_category, risk_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment["id"],
            payment["order_id"],
            payment["customer_id"],
            int(payment["amount"]),
            payment["method"],
            payment["bank"],
            payment.get("status", "failed"),
            payment["failure_code"],
            payment["created_at"],
            int(payment["hour"]),
            int(payment["day_of_week"]),
            int(payment["attempt_number"]),
            int(payment["time_since_last_attempt"]),
            payment["merchant_category"],
            float(payment["risk_score"]),
        ),
    )


def record_webhook_event(
    conn: sqlite3.Connection,
    event_id: str,
    event_type: str,
    payment_id: str | None,
    raw_payload: str,
    status: str = "received",
) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO webhook_events (
                event_id, event_type, payment_id, received_at, processed_at, status, raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                payment_id,
                datetime.now(timezone.utc).isoformat(),
                None,
                status,
                raw_payload,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def mark_webhook_processed(conn: sqlite3.Connection, event_id: str, payment_id: str | None, status: str) -> None:
    conn.execute(
        """
        UPDATE webhook_events
        SET processed_at = ?, payment_id = COALESCE(?, payment_id), status = ?
        WHERE event_id = ?
        """,
        (datetime.now(timezone.utc).isoformat(), payment_id, status, event_id),
    )


def log_decision(conn: sqlite3.Connection, payment_id: str, decision: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO agent_logs (
            payment_id, recommended_action, final_action, reason, confidence, policy_status,
            probabilities_json, analysis_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_id,
            decision["recommended_action"],
            decision["final_action"],
            decision["reason"],
            float(decision["confidence"]),
            decision["policy"]["status"],
            json.dumps(decision["probabilities"]),
            json.dumps(decision["analysis"]),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def log_attempt(
    conn: sqlite3.Connection,
    payment: dict[str, Any],
    decision: dict[str, Any],
    gateway_payload: dict[str, Any],
    result: str,
    amount_recovered: int,
) -> None:
    final_action = decision["final_action"]
    conn.execute(
        """
        INSERT INTO recovery_attempts (
            payment_id, action, probability, expected_value, executed_at, result,
            amount_recovered, gateway_payload, customer_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment["id"],
            final_action,
            float(decision["probabilities"].get(final_action, 0.0)),
            float(decision["expected_values"].get(final_action, 0.0)),
            datetime.now(timezone.utc).isoformat(),
            result,
            int(amount_recovered),
            json.dumps(gateway_payload),
            json.dumps(decision["customer_message"]),
        ),
    )
    status = "recovered" if amount_recovered > 0 else ("pending_review" if final_action == "human_review" else "recovery_attempted")
    conn.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment["id"]))


def latest_decision(conn: sqlite3.Connection, payment_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM agent_logs
        WHERE payment_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (payment_id,),
    ).fetchone()
    if not row:
        return None
    data = row_to_dict(row) or {}
    data["probabilities"] = json.loads(data.pop("probabilities_json"))
    data["analysis"] = json.loads(data.pop("analysis_json"))
    return data


def latest_attempt(conn: sqlite3.Connection, payment_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM recovery_attempts
        WHERE payment_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (payment_id,),
    ).fetchone()
    if not row:
        return None
    data = row_to_dict(row) or {}
    data["gateway_payload"] = json.loads(data["gateway_payload"])
    data["customer_message"] = json.loads(data["customer_message"])
    return data


def payment_audit_trail(conn: sqlite3.Connection, payment_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    payment = get_payment(conn, payment_id)
    if payment:
        events.append(
            {
                "timestamp": payment["created_at"],
                "payment_id": payment_id,
                "event": "Payment failure received",
                "reason": f"{payment['failure_code']} on {payment['method'].upper()} via {payment['bank']}",
                "model_confidence": None,
                "policy_result": None,
                "execution_result": payment["status"],
            }
        )

    logs = conn.execute(
        """
        SELECT * FROM agent_logs
        WHERE payment_id = ?
        ORDER BY id ASC
        """,
        (payment_id,),
    ).fetchall()
    prior_keys: set[tuple[str, str]] = set()
    for row in logs:
        log_key = (row["final_action"], row["reason"])
        is_recheck = log_key in prior_keys
        prior_keys.add(log_key)
        events.append(
            {
                "timestamp": row["created_at"],
                "payment_id": payment_id,
                "event": f"Policy re-check before execution: {row['final_action']}" if is_recheck else f"Agent decision generated: {row['final_action']}",
                "reason": f"Revalidated model score and policy gate before execution. {row['reason']}" if is_recheck else row["reason"],
                "model_confidence": row["confidence"],
                "policy_result": row["policy_status"],
                "execution_result": "revalidated" if is_recheck else None,
            }
        )

    attempts = conn.execute(
        """
        SELECT * FROM recovery_attempts
        WHERE payment_id = ?
        ORDER BY id ASC
        """,
        (payment_id,),
    ).fetchall()
    for row in attempts:
        events.append(
            {
                "timestamp": row["executed_at"],
                "payment_id": payment_id,
                "event": f"Recovery action executed: {row['action']}",
                "reason": f"Gateway result was {row['result']}; recovered amount {row['amount_recovered']}.",
                "model_confidence": row["probability"],
                "policy_result": "allowed" if row["action"] != "human_review" else "review",
                "execution_result": row["result"],
            }
        )

    return sorted(events, key=lambda item: item["timestamp"] or "")


def list_payments(conn: sqlite3.Connection, limit: int = 80) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.*, c.name, c.phone, c.email, c.customer_previous_success,
               c.customer_previous_failures, c.customer_age_days, c.previous_recovery_success
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        ORDER BY p.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    payments = [payment_from_row(row) for row in rows]
    for payment in payments:
        payment["latest_decision"] = latest_decision(conn, payment["id"])
        payment["latest_attempt"] = latest_attempt(conn, payment["id"])
    return payments


def metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payments").fetchone()
    failed = conn.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payments WHERE status = 'failed'").fetchone()
    recovered = conn.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount_recovered), 0) AS amount FROM recovery_attempts WHERE amount_recovered > 0").fetchone()
    pending_review = conn.execute("SELECT COUNT(*) AS count FROM payments WHERE status = 'pending_review'").fetchone()
    attempts = conn.execute("SELECT COUNT(*) AS count FROM recovery_attempts").fetchone()
    unnecessary = conn.execute("SELECT COUNT(*) AS count FROM recovery_attempts WHERE result IN ('failed', 'skipped')").fetchone()
    webhook_count = conn.execute("SELECT COUNT(*) AS count FROM webhook_events").fetchone()

    total_amount = float(total["amount"] or 0)
    recovered_amount = float(recovered["amount"] or 0)
    decision_rows = conn.execute(
        """
        SELECT p.id, p.amount, p.status, a.final_action, a.policy_status, a.probabilities_json
        FROM payments p
        LEFT JOIN agent_logs a ON a.id = (
            SELECT id FROM agent_logs WHERE payment_id = p.id ORDER BY id DESC LIMIT 1
        )
        """
    ).fetchall()

    eligible_actions = {"retry_immediate", "retry_30m", "payment_link", "alternate_method"}
    eligible_count = 0
    eligible_amount = 0.0
    expected_recovery = 0.0
    blocked_count = 0
    auto_recoverable_count = 0
    auto_recoverable_amount = 0.0

    for row in decision_rows:
        final_action = row["final_action"]
        amount = float(row["amount"] or 0)
        if final_action in eligible_actions:
            eligible_count += 1
            eligible_amount += amount
            auto_recoverable_count += 1
            auto_recoverable_amount += amount
            try:
                probabilities = json.loads(row["probabilities_json"] or "{}")
            except json.JSONDecodeError:
                probabilities = {}
            expected_recovery += amount * float(probabilities.get(final_action, 0.0))
        elif final_action == "human_review" or row["policy_status"] == "blocked":
            blocked_count += 1

    recovered_count = int(recovered["count"] or 0)
    payment_recovery_rate = recovered_count / eligible_count if eligible_count else 0.0
    revenue_recovery_rate = recovered_amount / eligible_amount if eligible_amount else 0.0

    blind_retry_recovered = int(total_amount * 0.22)
    blind_attempts = int(total["count"] or 0)
    ai_attempts = int(attempts["count"] or 0)
    ai_unnecessary = int(unnecessary["count"] or 0)
    blind_unnecessary = max(0, int(blind_attempts * 0.50))
    traditional_recovered_count = int(eligible_count * 0.22)
    traditional_recovered_amount = int(eligible_amount * 0.22)

    action_rows = conn.execute(
        """
        SELECT action, COUNT(*) AS count, COALESCE(SUM(amount_recovered), 0) AS recovered
        FROM recovery_attempts
        GROUP BY action
        ORDER BY count DESC
        """
    ).fetchall()

    return {
        "payments": {
            "total_count": int(total["count"] or 0),
            "total_amount": int(total_amount),
            "revenue_at_risk": int(total_amount),
            "failed_count": int(failed["count"] or 0),
            "failed_amount": int(failed["amount"] or 0),
            "eligible_count": eligible_count,
            "eligible_amount": int(eligible_amount),
            "auto_recoverable_count": auto_recoverable_count,
            "auto_recoverable_amount": int(auto_recoverable_amount),
            "expected_recovery_opportunity": int(expected_recovery),
            "blocked_count": blocked_count,
            "recovered_count": recovered_count,
            "recovered_amount": int(recovered_amount),
            "realized_recovery_amount": int(recovered_amount),
            "pending_review_count": int(pending_review["count"] or 0),
            "recovery_rate": round(payment_recovery_rate, 4),
            "payment_recovery_rate": round(payment_recovery_rate, 4),
            "revenue_recovery_rate": round(revenue_recovery_rate, 4),
            "webhook_events": int(webhook_count["count"] or 0),
        },
        "counterfactual": {
            "traditional": {
                "failed_payments": int(total["count"] or 0),
                "retries": blind_attempts,
                "recovered_payments": traditional_recovered_count,
                "recovered_amount": traditional_recovered_amount,
                "recovery_rate": round(traditional_recovered_count / eligible_count, 4) if eligible_count else 0.0,
                "unnecessary_attempts": blind_unnecessary,
            },
            "recoverai": {
                "failed_payments": int(total["count"] or 0),
                "retries": ai_attempts,
                "recovered_payments": recovered_count,
                "recovered_amount": int(recovered_amount),
                "recovery_rate": round(payment_recovery_rate, 4),
                "unnecessary_attempts": ai_unnecessary,
                "human_escalations": int(pending_review["count"] or 0),
                "blocked_actions": blocked_count,
            },
            "incremental_revenue": int(recovered_amount - traditional_recovered_amount),
            "unnecessary_attempt_reduction": round((blind_unnecessary - ai_unnecessary) / blind_unnecessary, 4) if blind_unnecessary else 0.0,
        },
        "root_causes": root_cause_insights(conn),
        "actions": [
            {
                "action": row["action"],
                "label": ACTIONS.get(row["action"], {}).get("label", row["action"]),
                "count": int(row["count"]),
                "recovered_amount": int(row["recovered"] or 0),
            }
            for row in action_rows
        ],
    }


def root_cause_insights(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT bank, method, failure_code, COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount
        FROM payments
        GROUP BY bank, method, failure_code
        ORDER BY count DESC, amount DESC
        LIMIT 5
        """
    ).fetchall()
    total_count = conn.execute("SELECT COUNT(*) AS count FROM payments").fetchone()["count"] or 1
    insights = []
    for row in rows:
        share = float(row["count"]) / float(total_count)
        expected_share = 1 / (len(["upi", "card", "netbanking", "wallet", "emi"]) * 8 * 11)
        lift = share / expected_share if expected_share else 0.0
        degradation = lift >= 4.0 and row["failure_code"] in {"BANK_ERROR", "GATEWAY_TIMEOUT", "NETWORK_ERROR"}
        insights.append(
            {
                "bank": row["bank"],
                "method": row["method"],
                "failure_code": row["failure_code"],
                "count": int(row["count"]),
                "amount": int(row["amount"] or 0),
                "share": round(share, 4),
                "lift": round(lift, 2),
                "degradation_detected": degradation,
                "likely_cause": "Bank-side degradation" if row["failure_code"] in {"BANK_ERROR", "GATEWAY_TIMEOUT"} else "Customer or payment-method friction",
                "recommendation": "Reduce immediate retries and route customers to alternate methods." if row["failure_code"] in {"BANK_ERROR", "GATEWAY_TIMEOUT"} else "Use contextual payment links and avoid repeated blind retries.",
            }
        )
    return insights


def recovery_report(conn: sqlite3.Connection) -> dict[str, Any]:
    summary = metrics(conn)
    rows = conn.execute(
        """
        SELECT p.id, p.order_id, p.amount, p.method, p.bank, p.failure_code, p.status,
               c.name AS customer_name,
               a.final_action, a.confidence, a.policy_status, a.reason,
               r.result, r.amount_recovered, r.executed_at
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN agent_logs a ON a.id = (
            SELECT id FROM agent_logs WHERE payment_id = p.id ORDER BY id DESC LIMIT 1
        )
        LEFT JOIN recovery_attempts r ON r.id = (
            SELECT id FROM recovery_attempts WHERE payment_id = p.id ORDER BY id DESC LIMIT 1
        )
        ORDER BY p.created_at DESC
        """
    ).fetchall()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "payments": [row_to_dict(row) for row in rows],
    }


def seed_demo_data(conn: sqlite3.Connection, agent: Any, gateway: Any, seed: int = 42) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM payments").fetchone()["count"]
    if existing:
        return

    rng = random.Random(seed)
    payments = generate_demo_failed_payments(seed=seed + 100)
    for payment in payments:
        insert_payment(conn, payment)

    conn.commit()

    seeded = list_payments(conn, limit=10000)
    for idx, payment in enumerate(seeded):
        if idx % 8 == 0:
            continue
        decision = agent.decide(payment)
        gateway_payload = gateway.execute(payment, decision)
        final_action = decision["final_action"]
        probability = true_recovery_probability(payment, final_action)
        if final_action in {"human_review", "no_retry"}:
            recovered = False
        else:
            recovered = rng.random() < probability
        amount_recovered = int(payment["amount"]) if recovered else 0
        result = "recovered" if recovered else ("queued_review" if final_action == "human_review" else "failed")
        log_decision(conn, payment["id"], decision)
        log_attempt(conn, payment, decision, gateway_payload, result, amount_recovered)
    conn.commit()
