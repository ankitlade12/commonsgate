"""Deterministic, agent-blind allocation engine."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .canonical import (
    candidate_manifest_hash,
    deterministic_rank,
    seed_commitment,
    sha256_hex,
)
from .models import AllocationResult, Charter, Request


class AllocationInvariantError(RuntimeError):
    """Raised when an internal safety invariant is violated."""


def _deduplicate(
    requests: Iterable[Request],
) -> tuple[list[Request], list[str], int]:
    grouped: dict[str, list[Request]] = defaultdict(list)
    for request in requests:
        grouped[request.principal_token].append(request)

    canonical: list[Request] = []
    review: list[str] = []
    duplicates = 0
    for principal_token, attempts in grouped.items():
        duplicates += len(attempts) - 1
        signatures = {attempt.fact_signature() for attempt in attempts}
        if len(signatures) != 1:
            review.append(principal_token)
            continue
        # request_id is used only to select an audit representative. It cannot
        # influence candidate ranking or eligibility.
        canonical.append(min(attempts, key=lambda attempt: attempt.request_id))

    return canonical, sorted(review), duplicates


def _ranked(
    candidates: Iterable[Request], *, seed: str, manifest_hash: str, bucket: str
) -> list[Request]:
    return sorted(
        candidates,
        key=lambda request: (
            deterministic_rank(
                seed=seed,
                manifest_hash=manifest_hash,
                bucket=bucket,
                principal_token=request.principal_token,
            ),
            request.principal_token,
        ),
    )


def _tier_ordered(
    candidates: Iterable[Request], *, seed: str, manifest_hash: str, purpose: str
) -> list[Request]:
    by_tier: dict[int, list[Request]] = defaultdict(list)
    for candidate in candidates:
        by_tier[candidate.priority_tier].append(candidate)

    ordered: list[Request] = []
    for tier in sorted(by_tier):
        ordered.extend(
            _ranked(
                by_tier[tier],
                seed=seed,
                manifest_hash=manifest_hash,
                bucket=f"{purpose}:tier:{tier}",
            )
        )
    return ordered


def allocate(
    requests: Iterable[Request], charter: Charter, *, seed: str
) -> AllocationResult:
    """Allocate capacity using only canonical policy facts.

    Conflicting duplicate submissions are routed to review instead of silently
    selecting the fastest or most favorable attempt.
    """

    if not seed:
        raise ValueError("a revealed non-empty seed is required")

    canonical, review, duplicate_count = _deduplicate(requests)
    eligible = [request for request in canonical if request.eligible]
    ineligible = sorted(
        request.principal_token for request in canonical if not request.eligible
    )
    manifest_hash = candidate_manifest_hash(
        request.policy_facts() for request in eligible
    )

    accommodation = [request for request in eligible if request.accommodation_requested]
    reserved_order = _tier_ordered(
        accommodation,
        seed=seed,
        manifest_hash=manifest_hash,
        purpose="accommodation-reservation",
    )
    reserved = reserved_order[: charter.reserved_accommodation_capacity]
    allocated_tokens = {request.principal_token for request in reserved}

    if charter.release_unused_reservations:
        general_capacity = charter.capacity - len(reserved)
    else:
        general_capacity = charter.capacity - charter.reserved_accommodation_capacity

    general_candidates = [
        request
        for request in eligible
        if request.principal_token not in allocated_tokens
    ]
    general_order = _tier_ordered(
        general_candidates,
        seed=seed,
        manifest_hash=manifest_hash,
        purpose="general",
    )
    general = general_order[:general_capacity]
    allocated = [*reserved, *general]
    allocated_tokens.update(request.principal_token for request in general)

    waitlist = [
        request
        for request in general_order
        if request.principal_token not in allocated_tokens
    ]
    allocated_principals = tuple(request.principal_token for request in allocated)
    waitlisted_principals = tuple(request.principal_token for request in waitlist)

    if len(allocated_principals) > charter.capacity:
        raise AllocationInvariantError("allocation exceeded capacity")
    if len(set(allocated_principals)) != len(allocated_principals):
        raise AllocationInvariantError("a principal received more than one allocation")

    reason_codes = {
        **{principal: "APPOINTMENT_OFFERED" for principal in allocated_principals},
        **{principal: "WAITLISTED" for principal in waitlisted_principals},
        **{principal: "OUTSIDE_SERVICE_AREA" for principal in ineligible},
        **{principal: "HUMAN_REVIEW_REQUIRED" for principal in review},
    }
    outcome_payload = {
        "charter": charter.public_rules(),
        "manifest_hash": manifest_hash,
        "seed_commitment": seed_commitment(seed),
        "allocated": allocated_principals,
        "waitlisted": waitlisted_principals,
        "ineligible": ineligible,
        "review": review,
        "reason_codes": reason_codes,
    }

    return AllocationResult(
        allocated_principals=allocated_principals,
        waitlisted_principals=waitlisted_principals,
        ineligible_principals=tuple(ineligible),
        review_principals=tuple(review),
        duplicate_attempts_neutralized=duplicate_count,
        manifest_hash=manifest_hash,
        seed_commitment=seed_commitment(seed),
        outcome_hash=sha256_hex(outcome_payload),
        reason_codes=reason_codes,
    )
