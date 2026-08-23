from __future__ import annotations

from commonsgate.contracts import (
    ExtractedFacts,
    NormalizationResult,
    RequestReceipt,
    RequestStatus,
)
from commonsgate.repository import InMemoryRepository


def receipt() -> RequestReceipt:
    return RequestReceipt(
        request_id="request-guard-test",
        round_id="round-guard-test",
        status=RequestStatus.RECEIVED,
        reason_code="RECEIVED",
        next_action="Wait.",
        policy_version="1.0.0",
        normalization=NormalizationResult(
            model_identifier="test-normalizer",
            facts=ExtractedFacts(
                service_area_confirmed=True,
                court_deadline_date=None,
                accommodation_requested=False,
            ),
            field_provenance={},
        ),
        correlation_id="correlation-guard-test",
    )


def test_repository_persists_idempotency_and_nonce_guards() -> None:
    repository = InMemoryRepository()
    stored_receipt = receipt()

    assert repository.get_idempotency("agent", "idempotency-key") is None
    repository.save_idempotency(
        "agent", "idempotency-key", "payload-hash", stored_receipt
    )
    payload_hash, restored = repository.get_idempotency(
        "agent", "idempotency-key"
    ) or ("", None)
    assert payload_hash == "payload-hash"
    assert restored == stored_receipt

    assert repository.consume_nonce("delegation", "nonce-value") is True
    assert repository.consume_nonce("delegation", "nonce-value") is False


def test_round_lease_blocks_another_worker_and_allows_release() -> None:
    repository = InMemoryRepository()

    assert repository.acquire_round_lease("round", "worker-one") is True
    assert repository.acquire_round_lease("round", "worker-two") is False
    repository.release_round_lease("round", "worker-one")
    assert repository.acquire_round_lease("round", "worker-two") is True
