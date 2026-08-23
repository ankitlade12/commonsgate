"""Metrics for measuring agent-mediated access inequality."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from .models import Request


def allocation_rates(
    requests: Iterable[Request], allocated_principals: Iterable[str]
) -> dict[str, float]:
    """Return unique-principal selection rates by experimental agent tier."""

    principal_tier: dict[str, str] = {}
    for request in requests:
        principal_tier.setdefault(request.principal_token, request.agent_tier)
    totals: dict[str, set[str]] = defaultdict(set)
    selected: dict[str, set[str]] = defaultdict(set)
    for principal, tier in principal_tier.items():
        totals[tier].add(principal)
    for principal in set(allocated_principals):
        if principal not in principal_tier:
            continue
        tier = principal_tier[principal]
        selected[tier].add(principal)
    return {
        tier: len(selected[tier]) / len(principals)
        for tier, principals in sorted(totals.items())
    }


def agent_advantage_index(rates: Mapping[str, float]) -> float:
    return max(rates.values()) - min(rates.values()) if rates else 0.0


def outcome_change_rate(
    left: Iterable[str], right: Iterable[str], population_size: int
) -> float:
    """Fraction of principals whose binary outcome changes between two runs."""

    if population_size <= 0:
        return 0.0
    return len(set(left).symmetric_difference(set(right))) / population_size
