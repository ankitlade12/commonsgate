import { NextRequest, NextResponse } from "next/server";

const languagePattern = /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/;

export async function GET(request: NextRequest) {
  const language = request.nextUrl.searchParams.get("language") ?? "en";
  if (!languagePattern.test(language)) {
    return NextResponse.json(
      { error: "Enter a valid BCP 47 language tag, such as hi, ar, sw-KE, or zh-Hant." },
      { status: 400 },
    );
  }

  const baseUrl = process.env.COMMONSGATE_API_URL ?? "http://127.0.0.1:8080";
  try {
    const response = await fetch(
      `${baseUrl}/v1/explanations/INCLUDED_IN_ROUND?language=${encodeURIComponent(language)}`,
      { cache: "no-store", signal: AbortSignal.timeout(2500) },
    );
    if (!response.ok) throw new Error(`Explanation API returned ${response.status}`);
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json({
      reason_code: "INCLUDED_IN_ROUND",
      requested_language: language,
      delivered_language: "en",
      title: "Included in the allocation round",
      message:
        "Your request meets the published intake rules and has one entry in this round. The kind or speed of agent you used does not change your chance.",
      next_action:
        "Wait for the intake window to close. Applying again will not improve your chance.",
      fallback_used: language.toLowerCase() !== "en",
      model_identifier: "approved-template-catalog",
      decision_authority: "none",
    });
  }
}
