from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app


def _chat_payload(message: str = "Hello") -> dict[str, str]:
    return {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": message,
    }


def test_chat_generates_correlation_id_and_enriched_redacted_log(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    messages = (
        "Email student@vinuni.edu.vn",
        "Phone 090 123 4567",
        "CCCD 001203004567",
        "Card 4111-1111-1111-1111",
    )
    with TestClient(app) as client:
        responses = [client.post("/chat", json=_chat_payload(message)) for message in messages]

    assert all(response.status_code == 200 for response in responses)
    assert all(
        re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])
        for response in responses
    )
    assert all(float(response.headers["x-response-time-ms"]) >= 0 for response in responses)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_logs = [record for record in records if record["event"] == "request_received"]
    request_log = request_logs[0]
    assert [record["correlation_id"] for record in request_logs] == [
        response.headers["x-request-id"] for response in responses
    ]
    assert request_log["user_id_hash"]
    assert request_log["session_id"] == "session-01"
    assert request_log["feature"] == "qa"
    assert request_log["model"]
    assert request_log["env"]
    serialized_log = json.dumps(request_logs)
    assert "student@" not in serialized_log
    assert "090 123 4567" not in serialized_log
    assert "001203004567" not in serialized_log
    assert "4111-1111-1111-1111" not in serialized_log
    preview = " ".join(record["payload"]["message_preview"] for record in request_logs)
    assert "REDACTED_EMAIL" in preview
    assert "REDACTED_PHONE_VN" in preview
    assert "REDACTED_CCCD" in preview
    assert "REDACTED_CREDIT_CARD" in preview


def test_chat_preserves_valid_request_id_and_replaces_invalid_one() -> None:
    with TestClient(app) as client:
        accepted = client.post(
            "/chat", json=_chat_payload(), headers={"x-request-id": "req-a1b2c3d4"}
        )
        replaced = client.post(
            "/chat", json=_chat_payload(), headers={"x-request-id": "unsafe-id"}
        )

    assert accepted.headers["x-request-id"] == "req-a1b2c3d4"
    assert re.fullmatch(r"req-[0-9a-f]{8}", replaced.headers["x-request-id"])
