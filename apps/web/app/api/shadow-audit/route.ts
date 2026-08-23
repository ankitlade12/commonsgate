import { NextRequest, NextResponse } from "next/server";
import { fallbackShadowAudit } from "../../../lib/evidence";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Record<string, unknown>;
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/v1/demo/shadow-audit`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json(fallbackShadowAudit);
  }
}
