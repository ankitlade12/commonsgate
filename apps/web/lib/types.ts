export type Tier = "manual" | "free" | "standard" | "premium";
export type EvidenceSource = "live" | "offline-demo";

export interface ProofBundle {
  evidence_source: EvidenceSource;
  proof_version: "commonsgate-proof-v1";
  scenario_id: "agent-access-200x20-v1";
  generated_at: string;
  synthetic_demo: true;
  population_size: number;
  capacity: number;
  total_attempts: number;
  retry_attempts_neutralized: number;
  baseline_unique_people_served: number;
  commonsgate_unique_people_served: number;
  baseline_agent_advantage_index: number;
  commonsgate_agent_advantage_index: number;
  individual_manual_to_premium_sensitivity: Record<string, number>;
  allocation_rates_by_agent_tier: Record<string, Record<Tier, number>>;
  counterfactual_outcome_change_rate: Record<Tier, number>;
  invariants: Record<string, boolean>;
  cryptographic_proof: {
    manifest_hash: string;
    seed_commitment: string;
    outcome_hash: string;
  };
}

export interface Explanation {
  evidence_source: EvidenceSource;
  reason_code: string;
  requested_language: string;
  delivered_language: string;
  title: string;
  message: string;
  next_action: string;
  fallback_used: boolean;
  model_identifier: string;
  decision_authority: "none";
}

export interface MetricInterval {
  mean: number;
  p10: number;
  p90: number;
}

export interface ShadowAuditReport {
  evidence_source: EvidenceSource;
  report_version: "commonsgate-shadow-v1";
  synthetic_demo: true;
  population_size: number;
  capacity: number;
  seed_runs: number;
  total_attempts: number;
  retry_attempts_neutralized: number;
  baseline_unique_people_served: number;
  baseline_agent_advantage_index: number;
  baseline_rates: Record<Tier, number | null>;
  commonsgate_agent_advantage_index: MetricInterval;
  commonsgate_rates: Record<Tier, MetricInterval | null>;
  exact_agent_counterfactual_change_rate: number;
  small_cell_threshold: number;
  suppressed_tiers: string[];
  report_hash: string;
}

export interface ThreatCheck {
  threat: string;
  control: string;
  passed: boolean;
  evidence: string;
}

export interface ThreatReport {
  evidence_source: EvidenceSource;
  report_version: "commonsgate-threats-v1";
  generated_at: string;
  checks: ThreatCheck[];
  passed_count: number;
  total_count: number;
  report_hash: string;
}

export interface RuntimeEvidence {
  status: "live" | "unavailable";
  evidence_source: EvidenceSource;
  normalizer: string;
  translator: string;
  repository: string;
  environment: string;
  service_revision: string;
  audit_chain_valid: boolean;
  cloud_trace_enabled: boolean;
  correlation_id: string;
}
