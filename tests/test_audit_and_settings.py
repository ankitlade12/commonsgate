from __future__ import annotations

import pytest

from commonsgate.audit import AuditLog
from commonsgate.settings import Settings


def test_audit_chain_is_valid_and_rejects_raw_sensitive_payload_keys() -> None:
    audit = AuditLog()
    audit.append(
        correlation_id="corr-1",
        actor_id="agent-1",
        action="REQUEST_SUBMITTED",
        object_type="request",
        object_id="request-1",
        payload={"raw_content_hash": "abc123"},
    )
    audit.append(
        correlation_id="corr-2",
        actor_id="provider-admin",
        action="ROUND_FROZEN",
        object_type="round",
        object_id="round-1",
    )
    assert audit.verify_chain() is True

    with pytest.raises(ValueError, match="prohibited audit payload"):
        audit.append(
            correlation_id="corr-3",
            actor_id="agent-1",
            action="UNSAFE_EVENT",
            object_type="request",
            object_id="request-1",
            payload={"raw_text": "must never enter the audit log"},
        )

    with pytest.raises(ValueError, match=r"payload\.context\[0\]\.token"):
        audit.append(
            correlation_id="corr-4",
            actor_id="agent-1",
            action="UNSAFE_NESTED_EVENT",
            object_type="request",
            object_id="request-1",
            payload={"context": [{"token": "nested-secret"}]},
        )


def test_audit_payload_is_snapshotted_before_hashing() -> None:
    audit = AuditLog()
    payload = {"context": {"reason_code": "INCLUDED_IN_ROUND"}}
    event = audit.append(
        correlation_id="corr-1",
        actor_id="agent-1",
        action="REQUEST_SUBMITTED",
        object_type="request",
        object_id="request-1",
        payload=payload,
    )

    payload["context"]["reason_code"] = "MUTATED"

    assert event.payload["context"]["reason_code"] == "INCLUDED_IN_ROUND"
    assert audit.verify_chain() is True


def test_settings_strip_secret_manager_newlines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMONSGATE_DELEGATION_SECRET", "  signing-secret\n")
    monkeypatch.setenv("COMMONSGATE_ADMIN_KEY", "admin-secret\n")
    monkeypatch.setenv("COMMONSGATE_PUBLIC_BASE_URL", " https://example.test/ \n")

    settings = Settings.from_env()

    assert settings.delegation_signing_secret == "signing-secret"
    assert settings.admin_key == "admin-secret"
    assert settings.public_base_url == "https://example.test/"


def test_production_refuses_demo_security_and_storage_modes() -> None:
    with pytest.raises(ValueError, match="signing secret"):
        Settings(environment="production")

    with pytest.raises(ValueError, match="NORMALIZER"):
        Settings(
            environment="production",
            delegation_signing_secret="a-real-looking-secret-value-over-32-characters",
            admin_key="a-real-looking-admin-key",
            normalizer_mode="rule",
            repository_mode="firestore",
        )

    with pytest.raises(ValueError, match="REPOSITORY"):
        Settings(
            environment="production",
            delegation_signing_secret="a-real-looking-secret-value-over-32-characters",
            admin_key="a-real-looking-admin-key",
            normalizer_mode="gemini",
            repository_mode="memory",
        )
