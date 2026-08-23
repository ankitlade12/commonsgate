from __future__ import annotations

from commonsgate.allocator import allocate
from commonsgate.models import Charter, Request


def request(
    principal: str,
    *,
    request_id: str | None = None,
    submitted_at_ms: int = 100,
    priority: int = 2,
    accommodation: bool = False,
    eligible: bool = True,
) -> Request:
    return Request(
        request_id=request_id or f"req-{principal}",
        principal_token=principal,
        agent_id="agent-demo",
        agent_tier="free",
        submitted_at_ms=submitted_at_ms,
        priority_tier=priority,
        accommodation_requested=accommodation,
        eligible=eligible,
    )


def charter(capacity: int = 3, reserved: int = 0) -> Charter:
    return Charter("demo", "1.0.0", capacity, reserved)


def test_never_exceeds_capacity_or_allocates_a_principal_twice() -> None:
    attempts = [request(f"p-{index}") for index in range(10)]
    attempts.extend(
        [request("p-0", request_id="retry-a"), request("p-0", request_id="retry-b")]
    )
    result = allocate(attempts, charter(), seed="seed")

    assert len(result.allocated_principals) == 3
    assert len(set(result.allocated_principals)) == 3
    assert result.duplicate_attempts_neutralized == 2


def test_arrival_order_and_retry_volume_cannot_change_the_outcome() -> None:
    originals = [request(f"p-{index}", submitted_at_ms=index) for index in range(12)]
    reversed_and_retried = list(reversed(originals)) + [
        request("p-3", request_id=f"retry-{index}", submitted_at_ms=0)
        for index in range(20)
    ]

    left = allocate(originals, charter(5), seed="fixed")
    right = allocate(reversed_and_retried, charter(5), seed="fixed")

    assert left.manifest_hash == right.manifest_hash
    assert left.allocated_principals == right.allocated_principals


def test_same_inputs_replay_to_same_hash() -> None:
    attempts = [request(f"p-{index}") for index in range(8)]
    left = allocate(attempts, charter(4), seed="replayable")
    right = allocate(attempts, charter(4), seed="replayable")

    assert left == right
    assert left.outcome_hash == right.outcome_hash


def test_priority_precedes_general_tie_breaking() -> None:
    attempts = [request("urgent-a", priority=1), request("urgent-b", priority=1)]
    attempts.extend(request(f"standard-{index}", priority=3) for index in range(20))

    result = allocate(attempts, charter(3), seed="priority")

    assert {"urgent-a", "urgent-b"}.issubset(result.allocated_principals)


def test_reservation_is_filled_and_unused_capacity_is_released() -> None:
    attempts = [request("accessible", priority=3, accommodation=True)]
    attempts.extend(request(f"general-{index}", priority=2) for index in range(8))

    result = allocate(attempts, charter(4, reserved=2), seed="reservation")

    assert "accessible" in result.allocated_principals
    assert len(result.allocated_principals) == 4


def test_conflicting_duplicate_facts_are_reviewed_not_gamed() -> None:
    attempts = [
        request("same-person", request_id="original", priority=3),
        request("same-person", request_id="favorable-retry", priority=1),
        request("other-person", priority=2),
    ]

    result = allocate(attempts, charter(2), seed="review")

    assert result.review_principals == ("same-person",)
    assert "same-person" not in result.allocated_principals
    assert result.reason_codes["same-person"] == "HUMAN_REVIEW_REQUIRED"
