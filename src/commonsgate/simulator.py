"""Synthetic baseline and CommonsGate comparison used by the demo and tests."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from .allocator import allocate
from .metrics import agent_advantage_index, allocation_rates, outcome_change_rate
from .models import AgentTier, AllocationResult, Charter, Request

DemoTier = Literal["manual", "free", "standard", "premium"]
DEMO_TIERS: tuple[DemoTier, ...] = ("manual", "free", "standard", "premium")
BASE_LATENCY_MS: dict[str, int] = {
    "manual": 45_000,
    "free": 18_000,
    "standard": 4_000,
    "premium": 100,
}
ATTEMPTS: dict[str, int] = {"manual": 1, "free": 1, "standard": 3, "premium": 8}


@dataclass(frozen=True, slots=True)
class SimulationReport:
    population_size: int
    capacity: int
    baseline_allocated_attempts: tuple[str, ...]
    baseline_unique_principals: tuple[str, ...]
    baseline_rates: dict[str, float]
    baseline_aai: float
    commonsgate: AllocationResult
    commonsgate_rates: dict[str, float]
    commonsgate_aai: float
    counterfactual_change_rates: dict[str, float]
    individual_agent_switch_sensitivity: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "population_size": self.population_size,
            "capacity": self.capacity,
            "baseline": {
                "allocated_attempts": self.baseline_allocated_attempts,
                "unique_principals": self.baseline_unique_principals,
                "allocation_rates_by_agent_tier": self.baseline_rates,
                "agent_advantage_index": self.baseline_aai,
            },
            "commonsgate": {
                **self.commonsgate.as_dict(),
                "allocation_rates_by_agent_tier": self.commonsgate_rates,
                "agent_advantage_index": self.commonsgate_aai,
            },
            "counterfactual_outcome_change_rate": self.counterfactual_change_rates,
            "individual_manual_to_premium_switch_sensitivity": (
                self.individual_agent_switch_sensitivity
            ),
        }


@dataclass(frozen=True, slots=True)
class ShadowAuditData:
    population_size: int
    capacity: int
    seed_runs: int
    total_attempts: int
    retry_attempts_neutralized: int
    baseline_unique_people_served: int
    baseline_rates: dict[str, float]
    baseline_aai: float
    commonsgate_aai_values: tuple[float, ...]
    commonsgate_rate_values: dict[str, tuple[float, ...]]
    exact_counterfactual_change_rate: float


@dataclass(frozen=True, slots=True)
class AgentSwapStudy:
    population_size: int
    capacity: int
    representations: tuple[DemoTier, ...]
    manifest_hashes: dict[DemoTier, str]
    outcome_hashes: dict[DemoTier, str]
    seed_commitment: str
    maximum_outcome_change_rate: float


def generate_requests(
    *, population_size: int = 200, scenario_seed: int = 17
) -> list[Request]:
    if population_size < len(DEMO_TIERS) or population_size % len(DEMO_TIERS):
        raise ValueError("population_size must be a positive multiple of four")

    rng = random.Random(scenario_seed)
    requests: list[Request] = []
    for index in range(population_size):
        tier = DEMO_TIERS[index % len(DEMO_TIERS)]
        principal = f"principal-{index:05d}"
        # Every tier gets the same repeating distribution of policy-relevant facts.
        stratum = index // len(DEMO_TIERS)
        priority = 1 if stratum % 25 == 0 else 2 if stratum % 5 == 0 else 3
        accommodation = stratum % 10 == 0
        jitter = rng.randrange(0, 700)
        for attempt in range(ATTEMPTS[tier]):
            requests.append(
                Request(
                    request_id=f"req-{index:05d}-{attempt:02d}",
                    principal_token=principal,
                    agent_id=f"{tier}-agent-{index % 7}",
                    agent_tier=tier,
                    submitted_at_ms=BASE_LATENCY_MS[tier] + jitter + attempt * 1_000,
                    priority_tier=priority,
                    accommodation_requested=accommodation,
                    retry_ordinal=attempt,
                )
            )
    return requests


def fifo_allocate(requests: list[Request], capacity: int) -> tuple[str, ...]:
    """Naive baseline: each attempt is a queue entry and earliest entries win."""

    ordered = sorted(requests, key=lambda item: (item.submitted_at_ms, item.request_id))
    return tuple(request.principal_token for request in ordered[:capacity])


def _retier_requests(requests: list[Request], tier: AgentTier) -> list[Request]:
    """Change only representation behavior while keeping people and facts fixed."""

    by_principal: dict[str, Request] = {}
    for request in requests:
        by_principal.setdefault(request.principal_token, request)
    transformed: list[Request] = []
    for index, request in enumerate(
        sorted(by_principal.values(), key=lambda item: item.principal_token)
    ):
        for attempt in range(ATTEMPTS[tier]):
            transformed.append(
                Request(
                    request_id=f"cf-{tier}-{index:05d}-{attempt:02d}",
                    principal_token=request.principal_token,
                    agent_id=f"{tier}-counterfactual-agent",
                    agent_tier=tier,
                    submitted_at_ms=BASE_LATENCY_MS[tier]
                    + (index % 700)
                    + attempt * 1_000,
                    priority_tier=request.priority_tier,
                    eligible=request.eligible,
                    accommodation_requested=request.accommodation_requested,
                    retry_ordinal=attempt,
                )
            )
    return transformed


def _switch_one_principal_to_premium(
    all_manual_requests: list[Request], principal_token: str
) -> list[Request]:
    unchanged = [
        request
        for request in all_manual_requests
        if request.principal_token != principal_token
    ]
    original = next(
        request
        for request in all_manual_requests
        if request.principal_token == principal_token
    )
    switched: list[Request] = []
    for attempt in range(ATTEMPTS["premium"]):
        switched.append(
            Request(
                request_id=f"switch-{principal_token}-{attempt:02d}",
                principal_token=principal_token,
                agent_id="premium-counterfactual-agent",
                agent_tier="premium",
                submitted_at_ms=BASE_LATENCY_MS["premium"] + attempt * 1_000,
                priority_tier=original.priority_tier,
                eligible=original.eligible,
                accommodation_requested=original.accommodation_requested,
                retry_ordinal=attempt,
            )
        )
    return [*unchanged, *switched]


def run_demo(
    *, population_size: int = 200, capacity: int = 20, seed: str = "demo-seed-v1"
) -> SimulationReport:
    requests = generate_requests(population_size=population_size)
    charter = Charter(
        charter_id="housing-legal-intake",
        version="1.0.0",
        capacity=capacity,
        reserved_accommodation_capacity=min(4, capacity),
    )
    baseline_attempts = fifo_allocate(requests, capacity)
    baseline_unique = tuple(dict.fromkeys(baseline_attempts))
    baseline_rates = allocation_rates(requests, baseline_unique)

    fair_result = allocate(requests, charter, seed=seed)
    fair_rates = allocation_rates(requests, fair_result.allocated_principals)

    reference = allocate(_retier_requests(requests, "manual"), charter, seed=seed)
    changes: dict[str, float] = {}
    for tier in DEMO_TIERS:
        counterfactual = allocate(_retier_requests(requests, tier), charter, seed=seed)
        changes[tier] = outcome_change_rate(
            reference.allocated_principals,
            counterfactual.allocated_principals,
            population_size,
        )

    baseline_reference = set(
        fifo_allocate(_retier_requests(requests, "manual"), capacity)
    )
    fair_reference = set(reference.allocated_principals)
    baseline_changed = 0
    fair_changed = 0
    for principal in sorted({request.principal_token for request in requests}):
        switched = _switch_one_principal_to_premium(
            _retier_requests(requests, "manual"), principal
        )
        baseline_switched = set(fifo_allocate(switched, capacity))
        fair_switched = set(allocate(switched, charter, seed=seed).allocated_principals)
        baseline_changed += (principal in baseline_reference) != (
            principal in baseline_switched
        )
        fair_changed += (principal in fair_reference) != (principal in fair_switched)

    return SimulationReport(
        population_size=population_size,
        capacity=capacity,
        baseline_allocated_attempts=baseline_attempts,
        baseline_unique_principals=baseline_unique,
        baseline_rates=baseline_rates,
        baseline_aai=agent_advantage_index(baseline_rates),
        commonsgate=fair_result,
        commonsgate_rates=fair_rates,
        commonsgate_aai=agent_advantage_index(fair_rates),
        counterfactual_change_rates=changes,
        individual_agent_switch_sensitivity={
            "fifo": baseline_changed / population_size,
            "commonsgate": fair_changed / population_size,
        },
    )


def run_shadow_audit(
    *, population_size: int, capacity: int, seed_runs: int
) -> ShadowAuditData:
    """Run a provider-facing synthetic comparison across committed seed variants.

    The repeated seeds measure outcome sampling variance. The agent counterfactual
    remains an exact property test: only agent representation changes while every
    policy fact stays fixed.
    """

    requests = generate_requests(population_size=population_size)
    charter = Charter(
        charter_id="shadow-audit",
        version="1.0.0",
        capacity=capacity,
        reserved_accommodation_capacity=min(max(capacity // 5, 0), capacity),
    )
    baseline_attempts = fifo_allocate(requests, capacity)
    baseline_unique = tuple(dict.fromkeys(baseline_attempts))
    baseline_rates = allocation_rates(requests, baseline_unique)

    aai_values: list[float] = []
    rate_values: dict[str, list[float]] = {tier: [] for tier in DEMO_TIERS}
    for index in range(seed_runs):
        result = allocate(requests, charter, seed=f"shadow-seed-{index:04d}")
        rates = allocation_rates(requests, result.allocated_principals)
        aai_values.append(agent_advantage_index(rates))
        for tier in DEMO_TIERS:
            rate_values[tier].append(rates[tier])

    reference = allocate(
        _retier_requests(requests, "manual"), charter, seed="shadow-invariance"
    )
    counterfactual_changes = []
    for tier in DEMO_TIERS:
        represented = allocate(
            _retier_requests(requests, tier), charter, seed="shadow-invariance"
        )
        counterfactual_changes.append(
            outcome_change_rate(
                reference.allocated_principals,
                represented.allocated_principals,
                population_size,
            )
        )

    return ShadowAuditData(
        population_size=population_size,
        capacity=capacity,
        seed_runs=seed_runs,
        total_attempts=len(requests),
        retry_attempts_neutralized=len(requests) - population_size,
        baseline_unique_people_served=len(baseline_unique),
        baseline_rates=baseline_rates,
        baseline_aai=agent_advantage_index(baseline_rates),
        commonsgate_aai_values=tuple(aai_values),
        commonsgate_rate_values={
            tier: tuple(values) for tier, values in rate_values.items()
        },
        exact_counterfactual_change_rate=max(counterfactual_changes, default=0.0),
    )


def run_agent_swap_study(
    *, population_size: int = 200, capacity: int = 20, seed: str = "demo-seed-v1"
) -> AgentSwapStudy:
    """Re-represent identical people and facts through every demo agent tier."""

    requests = generate_requests(population_size=population_size)
    charter = Charter(
        charter_id="housing-legal-intake",
        version="1.0.0",
        capacity=capacity,
        reserved_accommodation_capacity=min(4, capacity),
    )
    results = {
        tier: allocate(_retier_requests(requests, tier), charter, seed=seed)
        for tier in DEMO_TIERS
    }
    reference = results["manual"].allocated_principals
    changes = (
        outcome_change_rate(
            reference,
            results[tier].allocated_principals,
            population_size,
        )
        for tier in DEMO_TIERS
    )
    return AgentSwapStudy(
        population_size=population_size,
        capacity=capacity,
        representations=DEMO_TIERS,
        manifest_hashes={
            tier: results[tier].manifest_hash for tier in DEMO_TIERS
        },
        outcome_hashes={tier: results[tier].outcome_hash for tier in DEMO_TIERS},
        seed_commitment=results["manual"].seed_commitment,
        maximum_outcome_change_rate=max(changes, default=0.0),
    )
