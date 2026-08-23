import { NextResponse } from "next/server";
import { getProof } from "../../../lib/proof";
import { offlineEvidenceAllowed } from "../../../lib/runtime";

export async function GET() {
  const proof = await getProof();
  return NextResponse.json(proof, {
    status: proof.evidence_source === "live" || offlineEvidenceAllowed() ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
