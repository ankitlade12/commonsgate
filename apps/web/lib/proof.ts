import type { ProofBundle } from "./types";

export const fallbackProof: ProofBundle = {
  evidence_source: "offline-demo",
  proof_version: "commonsgate-proof-v1",
  scenario_id: "agent-access-200x20-v1",
  generated_at: "2026-08-22T00:00:00.000Z",
  synthetic_demo: true,
  population_size: 200,
  capacity: 20,
  total_attempts: 650,
  retry_attempts_neutralized: 450,
  baseline_unique_people_served: 20,
  commonsgate_unique_people_served: 20,
  baseline_agent_advantage_index: 0.4,
  commonsgate_agent_advantage_index: 0.04,
  individual_manual_to_premium_sensitivity: { fifo: 0.9, commonsgate: 0 },
  allocation_rates_by_agent_tier: {
    fifo: { manual: 0, free: 0, standard: 0, premium: 0.4 },
    commonsgate: { manual: 0.12, free: 0.12, standard: 0.08, premium: 0.08 },
  },
  counterfactual_outcome_change_rate: {
    manual: 0,
    free: 0,
    standard: 0,
    premium: 0,
  },
  invariants: {
    capacity_respected: true,
    one_person_one_chance: true,
    retry_invariant: true,
    agent_tier_invariant: true,
    language_excluded_from_allocation: true,
    deterministic_replay: true,
  },
  cryptographic_proof: {
    manifest_hash: "4fdc947998c2cfc7c6039afb8c8a9bb94a4fe6db7ba9287de782e867915b1baf",
    seed_commitment: "e72f1d53e04f618e2d1bb4dae62fe532e5e91613c62620139e48d0823b805d12",
    outcome_hash: "b784864f2805e8890e1746b79bf5f7c7c8bc0e6eb6943c3df4bd078257449828",
  },
};

export async function getProof(): Promise<ProofBundle> {
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/v1/demo/proof`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1200),
    });
    if (!response.ok) throw new Error(`Proof API returned ${response.status}`);
    return { ...((await response.json()) as ProofBundle), evidence_source: "live" };
  } catch {
    return { ...fallbackProof, generated_at: new Date().toISOString(), evidence_source: "offline-demo" };
  }
}
