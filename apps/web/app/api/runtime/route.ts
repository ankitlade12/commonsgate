import { NextResponse } from "next/server";
import { getRuntimeEvidence } from "../../../lib/runtime";

export async function GET() {
  const runtime = await getRuntimeEvidence();
  return NextResponse.json(runtime, {
    // This route reports runtime state to the UI; unavailability is valid data.
    // Readiness monitoring belongs on /api/health, which returns 503 when down.
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}
