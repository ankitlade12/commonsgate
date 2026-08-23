from __future__ import annotations

from hypothesis import given, strategies as st

from commonsgate.allocator import allocate
from commonsgate.models import Charter, Request


@given(
    priorities=st.lists(st.integers(min_value=1, max_value=3), min_size=1, max_size=60),
    capacity=st.integers(min_value=0, max_value=70),
)
def test_allocation_is_permutation_invariant(
    priorities: list[int], capacity: int
) -> None:
    requests = [
        Request(
            request_id=f"request-{index}",
            principal_token=f"principal-token-{index:04d}",
            agent_id=f"agent-{index % 4}",
            agent_tier=("manual", "free", "standard", "premium")[index % 4],
            submitted_at_ms=index,
            priority_tier=priority,
            accommodation_requested=index % 9 == 0,
        )
        for index, priority in enumerate(priorities)
    ]
    charter = Charter(
        "property-test",
        "1.0.0",
        capacity=min(capacity, len(requests)),
        reserved_accommodation_capacity=min(2, capacity, len(requests)),
    )

    forward = allocate(requests, charter, seed="fixed-property-seed")
    backward = allocate(list(reversed(requests)), charter, seed="fixed-property-seed")

    assert forward.manifest_hash == backward.manifest_hash
    assert forward.allocated_principals == backward.allocated_principals
    assert len(forward.allocated_principals) <= charter.capacity
    assert len(set(forward.allocated_principals)) == len(forward.allocated_principals)


@given(retry_count=st.integers(min_value=1, max_value=50))
def test_retry_volume_cannot_change_allocation(retry_count: int) -> None:
    base = [
        Request(
            request_id=f"request-{index}",
            principal_token=f"principal-token-{index:04d}",
            agent_id="free-agent",
            agent_tier="free",
            submitted_at_ms=index * 100,
            priority_tier=2,
        )
        for index in range(20)
    ]
    retries = [
        Request(
            request_id=f"retry-{index}",
            principal_token="principal-token-0007",
            agent_id="premium-agent",
            agent_tier="premium",
            submitted_at_ms=0,
            priority_tier=2,
            retry_ordinal=index + 1,
        )
        for index in range(retry_count)
    ]
    charter = Charter("property-test", "1.0.0", capacity=5)

    original = allocate(base, charter, seed="fixed-property-seed")
    flooded = allocate([*base, *retries], charter, seed="fixed-property-seed")

    assert original.manifest_hash == flooded.manifest_hash
    assert original.allocated_principals == flooded.allocated_principals
