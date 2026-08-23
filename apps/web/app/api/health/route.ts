import { NextResponse } from "next/server";
import { getRuntimeEvidence } from "../../../lib/runtime";

export async function GET() {
  const runtime = await getRuntimeEvidence();
  return NextResponse.json(
    {
      status: runtime.status === "live" ? "healthy" : "degraded",
      backend: runtime,
    },
    {
      status: runtime.status === "live" ? 200 : 503,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
