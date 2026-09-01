from __future__ import annotations

import json
import mimetypes
import os
import csv
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recoverai.constants import BANKS, FAILURE_CODES, MERCHANT_CATEGORIES, PAYMENT_METHODS
from recoverai.service import create_service


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
SERVICE = create_service()


class RecoverAIHandler(BaseHTTPRequestHandler):
    server_version = "RecoverAI/1.0"

    def do_OPTIONS(self) -> None:
        self._send_status(204)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/health":
            self._send_json(SERVICE.health())
            return
        if path == "/api/metrics":
            self._send_json(SERVICE.metrics())
            return
        if path == "/api/options":
            self._send_json(
                {
                    "payment_methods": PAYMENT_METHODS,
                    "banks": BANKS,
                    "failure_codes": FAILURE_CODES,
                    "merchant_categories": MERCHANT_CATEGORIES,
                }
            )
            return
        if path == "/api/report":
            report = SERVICE.report()
            if query.get("format", ["json"])[0].lower() == "csv":
                self._send_text(self._report_csv(report), content_type="text/csv; charset=utf-8")
                return
            self._send_json(report)
            return
        if path == "/api/payments":
            limit = int(query.get("limit", ["80"])[0])
            self._send_json({"payments": SERVICE.payments(limit=limit)})
            return
        if path.startswith("/api/payments/"):
            payment_id = path.removeprefix("/api/payments/").strip("/")
            payment = SERVICE.payment_detail(payment_id)
            if not payment:
                self._send_json({"error": "payment_not_found"}, status=404)
                return
            self._send_json(payment)
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/payments/simulate-failure":
            self._send_json(SERVICE.simulate_failure(), status=201)
            return
        if path == "/api/payments/manual":
            try:
                self._send_json(SERVICE.create_manual_payment(self._read_body()), status=201)
            except ValueError as exc:
                self._send_json({"error": "validation_error", "message": str(exc)}, status=400)
            return
        if path == "/api/predict-recovery":
            try:
                self._send_json(SERVICE.preview_manual_payment(self._read_body()))
            except ValueError as exc:
                self._send_json({"error": "validation_error", "message": str(exc)}, status=400)
            return
        if path == "/api/demo/reset":
            self._send_json(SERVICE.reset_demo())
            return
        if path == "/api/webhooks/razorpay":
            raw_body = self._read_raw_body()
            result = SERVICE.ingest_razorpay_webhook(raw_body, dict(self.headers.items()))
            status = 200 if result.get("accepted") else 401
            self._send_json(result, status=status)
            return
        if path == "/api/batch-run":
            body = self._read_body()
            limit = int(body.get("limit", 40))
            self._send_json(SERVICE.batch_run(limit=limit))
            return
        if path == "/api/batch-simulation":
            body = self._read_body()
            count = int(body.get("count", 10000))
            self._send_json(SERVICE.batch_simulation(count=count))
            return
        if path.startswith("/api/payments/") and path.endswith("/decide"):
            payment_id = path.removeprefix("/api/payments/").removesuffix("/decide").strip("/")
            try:
                self._send_json(SERVICE.decide(payment_id))
            except KeyError:
                self._send_json({"error": "payment_not_found"}, status=404)
            return
        if path.startswith("/api/payments/") and path.endswith("/execute"):
            payment_id = path.removeprefix("/api/payments/").removesuffix("/execute").strip("/")
            try:
                self._send_json(SERVICE.execute(payment_id))
            except KeyError:
                self._send_json({"error": "payment_not_found"}, status=404)
            return

        self._send_json({"error": "not_found"}, status=404)

    def _read_body(self) -> dict:
        raw = self._read_raw_body()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _read_raw_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _report_csv(self, report: dict) -> str:
        output = io.StringIO()
        fieldnames = [
            "id",
            "order_id",
            "amount",
            "method",
            "bank",
            "failure_code",
            "status",
            "customer_name",
            "final_action",
            "confidence",
            "policy_status",
            "result",
            "amount_recovered",
            "executed_at",
            "reason",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["payments"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
        return output.getvalue()

    def _serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = FRONTEND_DIR / "index.html"
        else:
            file_path = (FRONTEND_DIR / path.lstrip("/")).resolve()

        try:
            file_path.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_status(403)
            return

        if not file_path.exists() or file_path.is_dir():
            self._send_status(404)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, payload: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
        data = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _send_status(self, status: int) -> None:
        self.send_response(status)
        self._cors()
        self.end_headers()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format: str, *args) -> None:
        print(f"[recoverai] {self.address_string()} - {format % args}")


def main() -> None:
    host = os.getenv("RECOVERAI_HOST", "0.0.0.0")
    port = int(os.getenv("RECOVERAI_PORT", os.getenv("PORT", "8000")))
    httpd = ThreadingHTTPServer((host, port), RecoverAIHandler)
    print(f"RecoverAI running at http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
