import { DemoClient } from "./demo-client";
import { getProof } from "../lib/proof";
import { getRuntimeEvidence } from "../lib/runtime";

export default async function Home() {
  const [proof, runtime] = await Promise.all([getProof(), getRuntimeEvidence()]);
  return <DemoClient initialProof={proof} initialRuntime={runtime} />;
}
