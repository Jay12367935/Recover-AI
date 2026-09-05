from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from recoverai.agent import RecoveryAgent
from recoverai.data import generate_demo_failed_payments, generate_historical_attempts
from recoverai.ml import RecoveryModel
from recoverai.policy import evaluate_policy
from recoverai.service import RecoverAIService


class RecoverAITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rows = generate_historical_attempts(count=1600, seed=11)
        cls.model = RecoveryModel()
        cls.model.train(rows, epochs=4, seed=11)

    def test_model_predicts_action_probabilities(self) -> None:
        payment = generate_demo_failed_payments(count=1, seed=20)[0]
        probabilities = self.model.predict_actions(payment)
        self.assertIn("payment_link", probabilities)
        self.assertTrue(all(0.0 < probability < 1.0 for probability in probabilities.values()))

    def test_policy_blocks_high_risk_money_moving_action(self) -> None:
        payment = generate_demo_failed_payments(seed=20)[1]
        result = evaluate_policy(payment, "payment_link")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["final_action"], "human_review")

    def test_agent_returns_policy_bounded_decision(self) -> None:
        payment = generate_demo_failed_payments(seed=20)[0]
        decision = RecoveryAgent(self.model).decide(payment)
        self.assertIn(decision["final_action"], decision["probabilities"])
        self.assertIn("reason", decision)
        self.assertIn("customer_message", decision)

    def test_service_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RecoverAIService(
                db_path=Path(temp_dir) / "recoverai.sqlite",
                model_path=Path(temp_dir) / "model.json",
                seed=12,
            )
            try:
                payment = service.simulate_failure()
                result = service.execute(payment["id"])
                self.assertIn(result["result"], {"recovered", "failed", "queued_review"})
                self.assertIn("counterfactual", service.metrics())
            finally:
                service.close()

    def test_payment_detail_contains_audit_trail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RecoverAIService(
                db_path=Path(temp_dir) / "recoverai.sqlite",
                model_path=Path(temp_dir) / "model.json",
                seed=14,
            )
            try:
                payment = service.simulate_failure()
                service.decide(payment["id"])
                service.execute(payment["id"])
                detail = service.payment_detail(payment["id"])

                self.assertIsNotNone(detail)
                self.assertGreaterEqual(len(detail["audit_trail"]), 2)
                self.assertIn("Payment failure received", detail["audit_trail"][0]["event"])
                self.assertTrue(any("Agent decision generated" in item["event"] for item in detail["audit_trail"]))
                self.assertTrue(any("Policy re-check before execution" in item["event"] for item in detail["audit_trail"]))
            finally:
                service.close()

    def test_service_reset_report_and_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RecoverAIService(
                db_path=Path(temp_dir) / "recoverai.sqlite",
                model_path=Path(temp_dir) / "model.json",
                seed=18,
            )
            try:
                reset_metrics = service.reset_demo()
                self.assertIn("counterfactual", reset_metrics)

                report = service.report()
                self.assertGreater(len(report["payments"]), 0)

                payload = {
                    "event": "payment.failed",
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": "pay_test_webhook",
                                "order_id": "order_test_webhook",
                                "amount": 499900,
                                "method": "upi",
                                "bank": "HDFC",
                                "error_code": "BANK_ERROR",
                                "created_at": 1788156000,
                                "notes": {
                                    "customer_name": "Test Webhook",
                                    "customer_previous_success": 8,
                                    "customer_previous_failures": 1,
                                },
                            }
                        }
                    },
                }
                result = service.ingest_razorpay_webhook(
                    json.dumps(payload).encode("utf-8"),
                    {"x-razorpay-event-id": "evt_test_webhook"},
                )
                self.assertTrue(result["accepted"])
                self.assertEqual(result["status"], "processed")

                duplicate = service.ingest_razorpay_webhook(
                    json.dumps(payload).encode("utf-8"),
                    {"x-razorpay-event-id": "evt_test_webhook"},
                )
                self.assertEqual(duplicate["status"], "duplicate")
            finally:
                service.close()

    def test_manual_payment_preview_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RecoverAIService(
                db_path=Path(temp_dir) / "recoverai.sqlite",
                model_path=Path(temp_dir) / "model.json",
                seed=25,
            )
            try:
                payload = {
                    "customer_name": "Manual Customer",
                    "amount": 4999,
                    "method": "upi",
                    "bank": "HDFC",
                    "failure_code": "BANK_ERROR",
                    "merchant_category": "ecommerce",
                    "customer_previous_success": 8,
                    "customer_previous_failures": 1,
                    "attempt_number": 1,
                    "time_since_last_attempt": 15,
                    "risk_score": 0.09,
                }
                preview = service.preview_manual_payment(payload)
                self.assertEqual(preview["payment"]["amount"], 4999)
                self.assertIn("probabilities", preview["decision"])

                saved = service.create_manual_payment(payload)
                self.assertTrue(saved["saved"])
                self.assertEqual(saved["payment"]["customer_name"], "Manual Customer")
                self.assertTrue(saved["payment"]["id"].startswith("PAY_SIM_"))
                self.assertEqual(saved["payment"]["customer_previous_success"], 8)
                self.assertEqual(saved["payment"]["customer_previous_failures"], 1)
                self.assertIsNotNone(saved["payment"]["latest_decision"])
                self.assertIn("8 successful and 1 failed", saved["decision"]["reason"])

                executed = service.execute(saved["payment"]["id"])
                self.assertEqual(executed["result"], "recovered")
                detail = service.payment_detail(saved["payment"]["id"])
                self.assertEqual(detail["status"], "recovered")
            finally:
                service.close()

    def test_batch_simulation_uses_consistent_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RecoverAIService(
                db_path=Path(temp_dir) / "recoverai.sqlite",
                model_path=Path(temp_dir) / "model.json",
                seed=31,
            )
            try:
                result = service.batch_simulation(count=250)
                self.assertEqual(result["dataset_size"], 250)
                self.assertEqual(result["pipeline"]["policy_checked"], 250)
                self.assertEqual(result["pipeline"]["recovery_actions"], 250)
                self.assertLessEqual(result["results"]["recovered_count"], result["results"]["eligible_count"])
                self.assertIn("incremental_revenue", result["results"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
