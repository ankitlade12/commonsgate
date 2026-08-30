import { NextResponse } from "next/server";

export async function GET() {
  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(`${baseUrl}/v1/demo/agent-swap-certificate`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) {
      throw new Error(`Certificate API returned ${response.status}`);
    }
    const payload = await response.json();
    return NextResponse.json(
      { ...payload, evidence_source: "live" },
      {
        headers: {
          "Cache-Control": "no-store",
          "Content-Disposition": 'attachment; filename="commonsgate-agent-swap-certificate.json"',
        },
      },
    );
  } catch {
    return NextResponse.json(
      {
        error: "Live agent-swap certificate unavailable",
        evidence_source: "offline-demo",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
