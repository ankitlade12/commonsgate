from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from commonsgate.auth import DelegationTokenService, ReplayProtector
from commonsgate.contracts import DelegationIssueRequest
from commonsgate.errors import CommonsGateError

SECRET = "test-delegation-secret-that-is-long-enough"


def issue_request(principal: str = "principal-token-0001") -> DelegationIssueRequest:
    return DelegationIssueRequest(
        principal_token=principal,
        agent_id="agent-free-1",
        provider_id="provider-demo",
        program_id="program-demo",
        scopes=frozenset({"submit", "read_status"}),
        expires_in_minutes=30,
    )


def test_delegation_is_bound_to_agent_principal_provider_program_and_scope() -> None:
    service = DelegationTokenService(SECRET)
    token, claims = service.issue(issue_request())

    verified = service.verify(
        token,
        agent_id="agent-free-1",
        provider_id="provider-demo",
        program_id="program-demo",
        principal_token="principal-token-0001",
        required_scope="submit",
    )
    assert verified.delegation_id == claims.delegation_id

    with pytest.raises(CommonsGateError) as error:
        service.verify(
            token,
            agent_id="different-agent",
            provider_id="provider-demo",
            program_id="program-demo",
            principal_token="principal-token-0001",
            required_scope="submit",
        )
    assert error.value.code == "DELEGATION_SCOPE_MISMATCH"


def test_tampered_and_expired_delegations_are_rejected() -> None:
    service = DelegationTokenService(SECRET)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    token, _ = service.issue(issue_request(), now=now)

    with pytest.raises(CommonsGateError) as tampered:
        service.verify(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            agent_id="agent-free-1",
            provider_id="provider-demo",
            program_id="program-demo",
            principal_token="principal-token-0001",
            required_scope="submit",
            now=now,
        )
    assert tampered.value.code == "DELEGATION_INVALID"

    with pytest.raises(CommonsGateError) as expired:
        service.verify(
            token,
            agent_id="agent-free-1",
            provider_id="provider-demo",
            program_id="program-demo",
            principal_token="principal-token-0001",
            required_scope="submit",
            now=now + timedelta(hours=1),
        )
    assert expired.value.code == "DELEGATION_SCOPE_MISMATCH"


def test_nonce_can_be_consumed_only_once_per_delegation() -> None:
    protector = ReplayProtector()
    protector.consume("delegation-1", "nonce-0000000001")

    with pytest.raises(CommonsGateError) as replay:
        protector.consume("delegation-1", "nonce-0000000001")
    assert replay.value.code == "REPLAY_DETECTED"

    protector.consume("delegation-2", "nonce-0000000001")
