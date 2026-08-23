import { NextResponse } from "next/server";
import { fallbackThreatReport } from "../../../lib/evidence";
import { offlineEvidenceAllowed } from "../../../lib/runtime";

export async function GET() {
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/v1/demo/threats`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error(`Threat API returned ${response.status}`);
    return NextResponse.json({ ...(await response.json()), evidence_source: "live" });
  } catch {
    return NextResponse.json(fallbackThreatReport, {
      status: offlineEvidenceAllowed() ? 200 : 503,
    });
  }
}
