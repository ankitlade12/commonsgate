import { NextResponse } from "next/server";
import { fallbackShadowAudit } from "../../../lib/evidence";
import { offlineEvidenceAllowed } from "../../../lib/runtime";

export async function POST() {
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/v1/demo/shadow-audit`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      // The public dashboard runs one bounded, reproducible study. Do not let
      // unauthenticated callers turn this proxy into arbitrary compute.
      body: JSON.stringify({
        population_size: 200,
        capacity: 20,
        seed_runs: 10,
        small_cell_threshold: 10,
      }),
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) throw new Error(`Shadow audit API returned ${response.status}`);
    const payload = await response.json();
    return NextResponse.json({ ...payload, evidence_source: "live" });
  } catch {
    return NextResponse.json(fallbackShadowAudit, {
      status: offlineEvidenceAllowed() ? 200 : 503,
    });
  }
}
