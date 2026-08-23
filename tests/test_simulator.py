from __future__ import annotations

from commonsgate.simulator import run_demo


def test_demo_exposes_baseline_agent_advantage_and_neutralizes_retries() -> None:
    report = run_demo()

    assert report.baseline_aai >= 0.20
    assert report.baseline_rates["premium"] > report.baseline_rates["manual"]
    assert report.commonsgate.duplicate_attempts_neutralized > 0
    assert len(report.commonsgate.allocated_principals) == report.capacity
    assert report.individual_agent_switch_sensitivity["fifo"] >= 0.50
    assert report.individual_agent_switch_sensitivity["commonsgate"] == 0.0


def test_representation_counterfactual_is_exactly_invariant() -> None:
    report = run_demo()

    assert report.counterfactual_change_rates == {
        "manual": 0.0,
        "free": 0.0,
        "standard": 0.0,
        "premium": 0.0,
    }
