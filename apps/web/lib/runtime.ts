import "server-only";

import type { RuntimeEvidence } from "./types";

export function offlineEvidenceAllowed(): boolean {
  return process.env.COMMONSGATE_ALLOW_OFFLINE_DEMO === "true" || process.env.NODE_ENV !== "production";
}

export async function getRuntimeEvidence(): Promise<RuntimeEvidence> {
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error(`Health API returned ${response.status}`);
    const payload = (await response.json()) as Omit<RuntimeEvidence, "status" | "evidence_source" | "correlation_id">;
    return {
      ...payload,
      status: "live",
      evidence_source: "live",
      correlation_id: response.headers.get("x-correlation-id") ?? "not-reported",
    };
  } catch {
    return {
      status: "unavailable",
      evidence_source: "offline-demo",
      normalizer: "not-connected",
      translator: "not-connected",
      repository: "not-connected",
      environment: process.env.NODE_ENV ?? "unknown",
      service_revision: "not-connected",
      audit_chain_valid: false,
      cloud_trace_enabled: false,
      correlation_id: "not-connected",
    };
  }
}
