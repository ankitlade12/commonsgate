"""Small immutable domain model used by the deterministic allocation boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AgentTier = Literal[
    "manual", "free", "standard", "premium", "caseworker", "adversarial"
]


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    principal_token: str
    agent_id: str
    agent_tier: AgentTier
    submitted_at_ms: int
    priority_tier: int
    eligible: bool = True
    accommodation_requested: bool = False
    retry_ordinal: int = 0

    def __post_init__(self) -> None:
        if not self.request_id or not self.principal_token:
            raise ValueError("request_id and principal_token are required")
        if self.priority_tier < 1:
            raise ValueError("priority_tier must be a positive integer")
        if self.submitted_at_ms < 0 or self.retry_ordinal < 0:
            raise ValueError("timestamps and retry ordinals cannot be negative")

    def policy_facts(self) -> dict[str, Any]:
        """Facts visible to the allocator; agent metadata is intentionally absent."""

        return {
            "principal_token": self.principal_token,
            "priority_tier": self.priority_tier,
            "eligible": self.eligible,
            "accommodation_requested": self.accommodation_requested,
        }

    def fact_signature(self) -> tuple[bool, int, bool]:
        return (self.eligible, self.priority_tier, self.accommodation_requested)


@dataclass(frozen=True, slots=True)
class Charter:
    charter_id: str
    version: str
    capacity: int
    reserved_accommodation_capacity: int = 0
    release_unused_reservations: bool = True

    def __post_init__(self) -> None:
        if not self.charter_id or not self.version:
            raise ValueError("charter_id and version are required")
        if self.capacity < 0:
            raise ValueError("capacity cannot be negative")
        if not 0 <= self.reserved_accommodation_capacity <= self.capacity:
            raise ValueError("reserved capacity must be between zero and capacity")

    def public_rules(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocated_principals: tuple[str, ...]
    waitlisted_principals: tuple[str, ...]
    ineligible_principals: tuple[str, ...]
    review_principals: tuple[str, ...]
    duplicate_attempts_neutralized: int
    manifest_hash: str
    seed_commitment: str
    outcome_hash: str
    reason_codes: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
