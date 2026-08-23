from __future__ import annotations

import httpx
import pytest

from commonsgate.scheduler import run_once


def test_scheduler_calls_steward_without_leaking_credentials() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["admin_key"] = request.headers["X-Admin-Key"]
        captured["correlation"] = request.headers["X-Correlation-ID"]
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "round_id": "round-demo",
                "status": "PUBLISHED",
                "transitions": ["ALLOCATION_PUBLISHED"],
                "paused_for_review": False,
                "pending_review_count": 0,
                "expired_offer_count": 0,
                "promoted_request_ids": ["request-2"],
                "idempotent_noop": False,
            },
        )

    environment = {
        "COMMONSGATE_API_URL": "https://api.example.test/",
        "COMMONSGATE_ROUND_ID": "round-demo",
        "COMMONSGATE_ADMIN_KEY": "top-secret",
        "COMMONSGATE_DEMO_ROUND_SEED": "seed-that-is-long-enough",
    }
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        summary = run_once(environment=environment, client=client)

    assert captured["url"] == (
        "https://api.example.test/v1/rounds/round-demo/steward/tick"
    )
    assert captured["admin_key"] == "top-secret"
    assert str(captured["correlation"]).startswith("scheduled-")
    assert "seed-that-is-long-enough" in str(captured["body"])
    assert "top-secret" not in str(summary)
    assert "seed-that-is-long-enough" not in str(summary)
    assert summary["promoted_count"] == 1


def test_scheduler_requires_all_configuration() -> None:
    with pytest.raises(ValueError, match="COMMONSGATE_ROUND_ID is required"):
        run_once(
            environment={
                "COMMONSGATE_API_URL": "https://api.example.test",
                "COMMONSGATE_ADMIN_KEY": "secret",
                "COMMONSGATE_DEMO_ROUND_SEED": "seed-that-is-long-enough",
            }
        )
