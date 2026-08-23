import { DemoClient } from "./demo-client";
import { getProof } from "../lib/proof";

export default async function Home() {
  const proof = await getProof();
  return <DemoClient initialProof={proof} />;
}
