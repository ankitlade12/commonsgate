"""Synthetic scoped delegation tokens and replay protection for the MVP.

This module demonstrates the protocol boundary. It is not production identity
proofing and deliberately makes no claim to solve Sybil resistance.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

from .canonical import canonical_json
from .contracts import DelegationClaims, DelegationIssueRequest
from .errors import CommonsGateError


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class DelegationTokenService:
    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("delegation signing secret must be at least 32 characters")
        self._secret = secret.encode("utf-8")

    def issue(
        self, request: DelegationIssueRequest, *, now: datetime | None = None
    ) -> tuple[str, DelegationClaims]:
        issued_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        claims = DelegationClaims(
            delegation_id=f"deleg_{uuid.uuid4().hex}",
            principal_token=request.principal_token,
            agent_id=request.agent_id,
            provider_id=request.provider_id,
            program_id=request.program_id,
            scopes=request.scopes,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(minutes=request.expires_in_minutes),
        )
        payload = _b64encode(
            canonical_json(claims.model_dump(mode="json")).encode("utf-8")
        )
        signature = _b64encode(
            hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest()
        )
        return f"cgd1.{payload}.{signature}", claims

    def verify(
        self,
        token: str,
        *,
        agent_id: str,
        provider_id: str,
        program_id: str,
        principal_token: str,
        required_scope: str,
        now: datetime | None = None,
    ) -> DelegationClaims:
        try:
            prefix, payload, signature = token.split(".")
            expected = _b64encode(
                hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest()
            )
            if prefix != "cgd1" or not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            claims = DelegationClaims.model_validate(json.loads(_b64decode(payload)))
        except Exception as exc:
            raise CommonsGateError(
                "DELEGATION_INVALID",
                "The delegation token is invalid.",
                status_code=403,
            ) from exc

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        mismatches: list[dict[str, str]] = []
        expected_values = {
            "agent_id": (claims.agent_id, agent_id),
            "provider_id": (claims.provider_id, provider_id),
            "program_id": (claims.program_id, program_id),
            "principal_token": (claims.principal_token, principal_token),
        }
        for field, (actual, expected_value) in expected_values.items():
            if actual != expected_value:
                mismatches.append(
                    {"field": field, "reason": "delegation_scope_mismatch"}
                )
        if required_scope not in claims.scopes:
            mismatches.append({"field": "scope", "reason": "action_not_delegated"})
        if claims.expires_at <= current:
            mismatches.append({"field": "expires_at", "reason": "delegation_expired"})
        if claims.issued_at > current + timedelta(minutes=1):
            mismatches.append({"field": "issued_at", "reason": "issued_in_future"})
        if mismatches:
            raise CommonsGateError(
                "DELEGATION_SCOPE_MISMATCH",
                "This agent is not authorized for the requested action.",
                status_code=403,
                details=mismatches,
            )
        return claims


class ReplayProtector:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def consume(self, delegation_id: str, nonce: str) -> None:
        if not 16 <= len(nonce) <= 256:
            raise CommonsGateError(
                "NONCE_INVALID", "A nonce of 16–256 characters is required."
            )
        key = (delegation_id, nonce)
        with self._lock:
            if key in self._seen:
                raise CommonsGateError(
                    "REPLAY_DETECTED",
                    "This request nonce has already been used.",
                    status_code=409,
                )
            self._seen.add(key)
