"""One-shot Cloud Run Job entry point for the autonomous round steward."""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Mapping

import httpx


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def run_once(
    *,
    environment: Mapping[str, str] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    """Advance the configured round once and return a privacy-safe summary."""

    env = os.environ if environment is None else environment
    api_url = _required(env, "COMMONSGATE_API_URL").rstrip("/")
    round_id = _required(env, "COMMONSGATE_ROUND_ID")
    admin_key = _required(env, "COMMONSGATE_ADMIN_KEY")
    seed = _required(env, "COMMONSGATE_DEMO_ROUND_SEED")
    correlation_id = f"scheduled-{uuid.uuid4().hex}"

    owns_client = client is None
    http_client = client or httpx.Client(timeout=60.0)
    try:
        response = http_client.post(
            f"{api_url}/v1/rounds/{round_id}/steward/tick",
            headers={
                "X-Admin-Key": admin_key,
                "X-Correlation-ID": correlation_id,
            },
            json={"seed": seed},
        )
        response.raise_for_status()
        body = response.json()
    finally:
        if owns_client:
            http_client.close()

    return {
        "event": "scheduled_steward_tick",
        "correlation_id": correlation_id,
        "round_id": body["round_id"],
        "status": body["status"],
        "transitions": body["transitions"],
        "paused_for_review": body["paused_for_review"],
        "pending_review_count": body["pending_review_count"],
        "expired_offer_count": body["expired_offer_count"],
        "promoted_count": len(body["promoted_request_ids"]),
        "idempotent_noop": body["idempotent_noop"],
    }


def main() -> None:
    try:
        summary = run_once()
    except (ValueError, httpx.HTTPError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "event": "scheduled_steward_tick_failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
