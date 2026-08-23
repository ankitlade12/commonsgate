import type { ShadowAuditReport, ThreatReport } from "./types";

export const fallbackShadowAudit: ShadowAuditReport = {
  evidence_source: "offline-demo",
  report_version: "commonsgate-shadow-v1",
  synthetic_demo: true,
  population_size: 200,
  capacity: 20,
  seed_runs: 10,
  total_attempts: 650,
  retry_attempts_neutralized: 450,
  baseline_unique_people_served: 20,
  baseline_agent_advantage_index: 0.4,
  baseline_rates: { manual: 0, free: 0, standard: 0, premium: 0.4 },
  commonsgate_agent_advantage_index: { mean: 0.06, p10: 0.04, p90: 0.1 },
  commonsgate_rates: {
    manual: { mean: 0.082, p10: 0.04, p90: 0.12 },
    free: { mean: 0.106, p10: 0.06, p90: 0.12 },
    standard: { mean: 0.104, p10: 0.08, p90: 0.14 },
    premium: { mean: 0.108, p10: 0.08, p90: 0.14 },
  },
  exact_agent_counterfactual_change_rate: 0,
  small_cell_threshold: 10,
  suppressed_tiers: [],
  report_hash: "b1474c0cf3a227f8798a293945f113663d57dcd75293472364a7738ec3a7604f",
};

export const fallbackThreatReport: ThreatReport = {
  evidence_source: "offline-demo",
  report_version: "commonsgate-threats-v1",
  generated_at: "2026-08-22T00:00:00.000Z",
  checks: [
    { threat: "retry_flood", control: "Principal-level canonicalization", passed: true, evidence: "450 retries neutralized" },
    { threat: "premium_agent_switch", control: "Agent metadata excluded from allocation", passed: true, evidence: "0.0% counterfactual outcome change across all agent tiers" },
    { threat: "capacity_overrun", control: "Allocator capacity invariant", passed: true, evidence: "20 of 20 slots allocated" },
    { threat: "seed_substitution", control: "Precommitted seed hash", passed: true, evidence: "Revealed seed matches the published commitment" },
    { threat: "outcome_tampering", control: "Deterministic replay", passed: true, evidence: "Independent replay reproduced the outcome hash" },
    { threat: "language_priority_leak", control: "Canonical policy-fact allowlist", passed: true, evidence: "Language is absent from every allocator input" },
  ],
  passed_count: 6,
  total_count: 6,
  report_hash: "8d6378209cc95207ef52e9e0d6dc331718a8a99df86c707c104271a6b2a6c57c",
};
