import { NextResponse } from "next/server";
import { getProof } from "../../../lib/proof";

export async function GET() {
  const proof = await getProof();
  return NextResponse.json(proof, {
    headers: { "Cache-Control": "no-store" },
  });
}
