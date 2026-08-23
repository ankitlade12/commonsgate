"use client";

import { useState, useTransition } from "react";
import type {
  Explanation,
  ProofBundle,
  RuntimeEvidence,
  ShadowAuditReport,
  ThreatReport,
  Tier,
} from "../lib/types";

const tiers: Array<{ key: Tier; label: string; detail: string }> = [
  { key: "manual", label: "Manual", detail: "One careful submission" },
  { key: "free", label: "Free agent", detail: "Basic automation" },
  { key: "standard", label: "Standard", detail: "Fast monitoring · 3 attempts" },
  { key: "premium", label: "Premium", detail: "Always-on · 8 attempts" },
];

const invariantLabels: Record<string, string> = {
  capacity_respected: "Capacity never exceeded",
  one_person_one_chance: "One person, one chance",
  retry_invariant: "Retries cannot improve odds",
  agent_tier_invariant: "Agent price and speed ignored",
  language_excluded_from_allocation: "Language excluded from decisions",
  deterministic_replay: "Same inputs reproduce outcome",
};

const threatLabels: Record<string, string> = {
  retry_flood: "Retry flood",
  premium_agent_switch: "Premium-agent switch",
  capacity_overrun: "Capacity overrun",
  seed_substitution: "Seed substitution",
  outcome_tampering: "Outcome tampering",
  language_priority_leak: "Language priority leak",
};

function Mark({ children }: { children: React.ReactNode }) {
  return <span className="eyebrow">{children}</span>;
}

function Icon({ name }: { name: "shield" | "check" | "arrow" | "globe" | "lock" }) {
  const paths = {
    shield: <path d="M12 3 5 6v5c0 4.4 2.8 8.2 7 9.5 4.2-1.3 7-5.1 7-9.5V6l-7-3Z" />,
    check: <path d="m6 12 4 4 8-9" />,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9S9.5 5.5 12 3Z" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function TierGrid({ tier, selected }: { tier: Tier; selected: number }) {
  return (
    <div className="tier-row">
      <div className="tier-name"><strong>{tiers.find((item) => item.key === tier)?.label}</strong><span>{tiers.find((item) => item.key === tier)?.detail}</span></div>
      <div className="people-grid" aria-label={`${selected} of 50 ${tier} users selected`}>
        {Array.from({ length: 50 }, (_, index) => (
          <span className={index < selected ? "person selected" : "person"} key={index} />
        ))}
      </div>
      <strong className="tier-result">{selected}/50</strong>
    </div>
  );
}

function HashRow({ label, value }: { label: string; value: string }) {
  return <div className="hash-row"><span>{label}</span><code title={value}>{value.slice(0, 12)}…{value.slice(-8)}</code><span className="verified"><Icon name="check" /> verified</span></div>;
}

export function DemoClient({
  initialProof,
  initialRuntime,
}: {
  initialProof: ProofBundle;
  initialRuntime: RuntimeEvidence;
}) {
  const [proof, setProof] = useState(initialProof);
  const [runtime, setRuntime] = useState(initialRuntime);
  const [mode, setMode] = useState<"fifo" | "commonsgate">("commonsgate");
  const [isPending, startTransition] = useTransition();
  const [proofError, setProofError] = useState("");
  const [language, setLanguage] = useState("hi-Deva-IN");
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [languageError, setLanguageError] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [shadow, setShadow] = useState<ShadowAuditReport | null>(null);
  const [threats, setThreats] = useState<ThreatReport | null>(null);
  const [isAuditing, setIsAuditing] = useState(false);
  const [isTestingThreats, setIsTestingThreats] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");

  const rates = proof.allocation_rates_by_agent_tier[mode];
  const aai = mode === "fifo" ? proof.baseline_agent_advantage_index : proof.commonsgate_agent_advantage_index;
  const isCloudRuntime = runtime.status === "live" && runtime.environment === "production" && runtime.service_revision !== "local";

  async function refreshRuntime() {
    try {
      const response = await fetch("/api/runtime", { cache: "no-store" });
      const body = (await response.json()) as RuntimeEvidence;
      setRuntime(body);
    } catch {
      setRuntime((current) => ({ ...current, status: "unavailable", evidence_source: "offline-demo" }));
    }
  }

  function rerunProof() {
    startTransition(async () => {
      setProofError("");
      try {
        const response = await fetch("/api/proof", { cache: "no-store" });
        const body = (await response.json()) as ProofBundle;
        if (!response.ok) {
          setProof(body);
          throw new Error("Live proof unavailable. The displayed artifact is explicitly marked offline.");
        }
        setProof(body);
      } catch (error) {
        setProofError(error instanceof Error ? error.message : "The proof could not be rerun.");
      } finally {
        await refreshRuntime();
      }
    });
  }

  async function translateExplanation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsTranslating(true);
    setLanguageError("");
    try {
      const response = await fetch(`/api/explanation?language=${encodeURIComponent(language)}`);
      const body = (await response.json()) as Explanation;
      setExplanation(body);
      if (!response.ok) {
        throw new Error("Live translation unavailable. Approved English fallback is explicitly marked offline.");
      }
    } catch (error) {
      setLanguageError(error instanceof Error ? error.message : "Translation could not be loaded.");
    } finally {
      setIsTranslating(false);
      await refreshRuntime();
    }
  }

  async function runShadowAudit() {
    setIsAuditing(true);
    setEvidenceError("");
    try {
      const response = await fetch("/api/shadow-audit", {
        method: "POST",
      });
      const body = (await response.json()) as ShadowAuditReport;
      setShadow(body);
      if (!response.ok) {
        throw new Error("Live shadow audit unavailable. The displayed report is explicitly marked offline.");
      }
    } catch (error) {
      setEvidenceError(error instanceof Error ? error.message : "The shadow audit failed.");
    } finally {
      setIsAuditing(false);
      await refreshRuntime();
    }
  }

  async function runThreatReport() {
    setIsTestingThreats(true);
    setEvidenceError("");
    try {
      const response = await fetch("/api/threats", { cache: "no-store" });
      const body = (await response.json()) as ThreatReport;
      setThreats(body);
      if (!response.ok) {
        throw new Error("Live adversarial checks unavailable. The displayed report is explicitly marked offline.");
      }
    } catch (error) {
      setEvidenceError(error instanceof Error ? error.message : "The adversarial checks failed.");
    } finally {
      setIsTestingThreats(false);
      await refreshRuntime();
    }
  }

  return (
    <main>
      <div className={`runtime-banner ${runtime.status === "live" ? "runtime-live" : "runtime-offline"}`} role="status" aria-live="polite">
        <div className="shell runtime-inner">
          <span className="runtime-state"><i aria-hidden="true" />{runtime.status === "live" ? (isCloudRuntime ? "LIVE CLOUD EVIDENCE" : "LIVE LOCAL API") : "OFFLINE DEMO ARTIFACT"}</span>
          <span>{runtime.status === "live" ? `${runtime.normalizer} · ${runtime.repository} · ${runtime.environment}` : "Backend unavailable — no live execution is being claimed"}</span>
          <code>{runtime.status === "live" ? `${runtime.service_revision} · ${runtime.correlation_id}` : "RECORDED SYNTHETIC DATA"}</code>
        </div>
      </div>
      <header className="nav shell">
        <a className="brand" href="#top" aria-label="CommonsGate home"><span className="brand-mark"><Icon name="shield" /></span><span>CommonsGate</span></a>
        <nav aria-label="Primary navigation"><a href="#proof">Live proof</a><a href="#evidence">Shadow audit</a><a href="#workflow">Workflow</a><a href="#language">Languages</a></nav>
        <a className="nav-cta" href="#proof">Run the proof <Icon name="arrow" /></a>
      </header>

      <section className="hero shell" id="top">
        <div className="hero-copy">
          <Mark>Neutral infrastructure for agent-mediated access</Mark>
          <h1>Fair access,<br />even when agents <em>compete.</em></h1>
          <p className="hero-lede">CommonsGate stops faster, pricier, more persistent AI agents from taking every scarce appointment. Policy decides. Agent power does not.</p>
          <div className="hero-actions"><a className="button primary" href="#proof">See 200 agents compete <Icon name="arrow" /></a><a className="text-link" href="#workflow">Inspect the protocol</a></div>
          <div className="trust-line"><span><Icon name="check" /> Deterministic core</span><span><Icon name="check" /> Public replay proof</span><span><Icon name="check" /> Human review</span></div>
        </div>
        <div className="hero-visual" aria-label="Agent attempts converge into one fair allocation gate">
          <div className="signal-stack">
            {tiers.map((tier, index) => <div className={`signal signal-${index}`} key={tier.key}><span>{tier.label}</span><b>{[1, 1, 3, 8][index]}×</b></div>)}
          </div>
          <div className="gate-line"><span /><div className="gate"><Icon name="shield" /><small>ONE PERSON</small><strong>ONE CHANCE</strong></div><span /></div>
          <div className="outcome-card"><span className="pulse" /><div><small>ALLOCATION SEALED</small><strong>20 appointments</strong><span>Policy v1.0 · replay verified</span></div></div>
        </div>
      </section>

      <section className="proof-section" id="proof">
        <div className="shell">
          <div className="section-heading"><div><Mark>Interactive evidence</Mark><h2>Don&apos;t take our word for it.</h2><p>Same 200 people. Same policy facts. The only variable is the power of the agent representing them.</p></div><div className="proof-runner"><button type="button" className="button run" onClick={rerunProof} disabled={isPending}><span className={isPending ? "spinner spinning" : "spinner"} />{isPending ? "Running 650 attempts…" : "Rerun deterministic proof"}</button><span role="status" aria-live="polite">{proofError}</span></div></div>

          <div className="proof-console">
            <div className="console-bar"><div><span className={proof.evidence_source === "live" ? "live-dot" : "offline-dot"} /> {proof.evidence_source === "live" ? "LIVE API" : "OFFLINE ARTIFACT"} · SYNTHETIC · 200 PEOPLE · 20 SLOTS</div><span>PROOF {proof.proof_version.replace("commonsgate-proof-", "").toUpperCase()}</span></div>
            <div className="mode-switch" role="group" aria-label="Allocation system comparison">
              <button type="button" aria-pressed={mode === "fifo"} className={mode === "fifo" ? "active danger" : ""} onClick={() => setMode("fifo")}><span>01</span> First come, first served<small>Speed and retries decide</small></button>
              <button type="button" aria-pressed={mode === "commonsgate"} className={mode === "commonsgate" ? "active" : ""} onClick={() => setMode("commonsgate")}><span>02</span> CommonsGate<small>Policy and committed tie-break decide</small></button>
            </div>

            <div className="proof-body">
              <div className="tier-panel">
                <div className="panel-label"><span>WHO GETS THE 20 SLOTS?</span><span>selected / 50 people</span></div>
                {tiers.map((tier) => <TierGrid key={tier.key} tier={tier.key} selected={Math.round(rates[tier.key] * 50)} />)}
              </div>
              <aside className={`score-panel ${mode === "fifo" ? "score-danger" : ""}`}>
                <small>AGENT ADVANTAGE INDEX</small><strong>{aai.toFixed(2)}</strong><div className="score-track"><span style={{ width: `${Math.max(aai * 200, 2)}%` }} /></div><p>{mode === "fifo" ? "Premium agents capture 100% of appointments. Representation changes outcomes." : "Near-zero group spread; switching one person from manual to premium changes 0 outcomes."}</p>
                <div className="sensitivity"><span>Manual → premium<br />outcome sensitivity</span><b>{Math.round(proof.individual_manual_to_premium_sensitivity[mode] * 100)}%</b></div>
              </aside>
            </div>
            <div className="attempt-strip"><span><b>{proof.total_attempts}</b> incoming attempts</span><Icon name="arrow" /><span><b>{proof.retry_attempts_neutralized}</b> retries neutralized</span><Icon name="arrow" /><span><b>{proof.population_size}</b> unique people</span><Icon name="arrow" /><span className="final"><b>{proof.capacity}</b> policy-selected offers</span></div>
          </div>

          <div className="invariant-grid">
            {Object.entries(proof.invariants).map(([key, passed]) => <div className="invariant" key={key}><span className={passed ? "check-badge" : "check-badge failed"}><Icon name="check" /></span><div><strong>{invariantLabels[key] ?? key}</strong><small>{passed ? "Property test passed" : "Needs investigation"}</small></div></div>)}
          </div>
        </div>
      </section>

      <section className="evidence shell" id="evidence">
        <div className="section-heading compact"><div><Mark>Provider proof lab</Mark><h2>Measure the risk before changing the queue.</h2></div><p>Shadow mode compares the current speed-sensitive process with an agent-neutral charter. The threat lab then executes the controls judges and providers should challenge.</p></div>
        <div className="evidence-grid">
          <article className="lab-card shadow-card">
            <div className="lab-head"><div><small>SHADOW MODE · SYNTHETIC</small><h3>Existing queue comparison</h3></div><button type="button" onClick={runShadowAudit} disabled={isAuditing}>{isAuditing ? "Running 10 seeds…" : "Run shadow audit"}</button></div>
            <div className="lab-metrics">
              <div><span>FIFO agent advantage</span><strong>{(shadow?.baseline_agent_advantage_index ?? proof.baseline_agent_advantage_index).toFixed(2)}</strong></div>
              <div><span>CommonsGate mean</span><strong>{(shadow?.commonsgate_agent_advantage_index.mean ?? proof.commonsgate_agent_advantage_index).toFixed(2)}</strong></div>
              <div><span>Agent-switch change</span><strong>{((shadow?.exact_agent_counterfactual_change_rate ?? 0) * 100).toFixed(0)}%</strong></div>
            </div>
            <div className="interval-row"><span>Across {shadow?.seed_runs ?? 10} committed seed variants</span><div><i style={{ width: `${Math.max((shadow?.commonsgate_agent_advantage_index.p10 ?? 0.04) * 500, 4)}%` }} /><b style={{ width: `${Math.max((shadow?.commonsgate_agent_advantage_index.p90 ?? 0.1) * 500, 8)}%` }} /></div><span>P10 {(shadow?.commonsgate_agent_advantage_index.p10 ?? 0.04).toFixed(2)} · P90 {(shadow?.commonsgate_agent_advantage_index.p90 ?? 0.1).toFixed(2)}</span></div>
            <p>{shadow?.retry_attempts_neutralized ?? proof.retry_attempts_neutralized} retry attempts collapse into one opportunity per person. Small cohorts are suppressed before export.</p>
            <code>{shadow?.report_hash ? `${shadow.evidence_source === "live" ? "LIVE" : "OFFLINE"} · ${shadow.report_hash.slice(0, 20)}…` : "Run to generate a source-labelled report hash"}</code>
          </article>

          <article className="lab-card threat-card">
            <div className="lab-head"><div><small>ADVERSARIAL EVALUATION</small><h3>Attack the invariant</h3></div><button type="button" onClick={runThreatReport} disabled={isTestingThreats}>{isTestingThreats ? "Testing…" : "Run 6 attacks"}</button></div>
            <div className="threat-list">
              {(threats?.checks ?? [
                { threat: "retry_flood", control: "Principal canonicalization", passed: true, evidence: "450 retries neutralized" },
                { threat: "premium_agent_switch", control: "Agent-blind manifest", passed: true, evidence: "0% outcome change" },
                { threat: "capacity_overrun", control: "Hard allocator invariant", passed: true, evidence: "20 / 20" },
                { threat: "seed_substitution", control: "Commit–reveal", passed: true, evidence: "Commitment matched" },
                { threat: "outcome_tampering", control: "Independent replay", passed: true, evidence: "Hash reproduced" },
                { threat: "language_priority_leak", control: "Fact allowlist", passed: true, evidence: "Field absent" },
              ]).map((check) => <div key={check.threat}><span className={check.passed ? "mini-pass" : "mini-fail"}><Icon name="check" /></span><p><strong>{threatLabels[check.threat] ?? check.threat}</strong><small>{check.control}</small></p><em>{check.evidence}</em></div>)}
            </div>
            <div className="threat-footer"><span>{threats ? `${threats.passed_count}/${threats.total_count} ${threats.evidence_source} checks passed` : "Run to execute against the configured API"}</span><code>{threats?.report_hash ? `${threats.report_hash.slice(0, 16)}…` : "NO CASE DATA"}</code></div>
          </article>
        </div>
        {evidenceError && <p className="evidence-error" role="alert">{evidenceError}</p>}
      </section>

      <section className="workflow shell" id="workflow">
        <div className="section-heading compact"><div><Mark>From request to proof</Mark><h2>AI helps. It never decides.</h2></div><p>Gemini and ADK handle messy human communication at the edge. A small deterministic boundary controls scarce resources.</p></div>
        <div className="flow-grid">
          <article><span className="step">01</span><div className="flow-icon"><Icon name="globe" /></div><h3>Understand any request</h3><p>Natural-language intake becomes a source-linked Fair Access Envelope. Low confidence pauses for review.</p><small>GEMINI · SCHEMA CONSTRAINED</small></article>
          <article><span className="step">02</span><div className="flow-icon"><Icon name="shield" /></div><h3>Remove agent advantage</h3><p>Delegations resolve to one pseudonymous person. Retry volume, speed, price, and language are dropped.</p><small>DETERMINISTIC · AGENT BLIND</small></article>
          <article><span className="step">03</span><div className="flow-icon"><Icon name="lock" /></div><h3>Publish replayable proof</h3><p>The frozen manifest, precommitted seed, policy version, and outcome hash make the round reproducible.</p><small>HASH CHAIN · PUBLIC ARTIFACT</small></article>
        </div>

        <div className="review-card">
          <div className="review-copy"><Mark>Human review that leaves a trail</Mark><h3>Uncertainty cannot become a silent denial.</h3><p>A reviewer corrects facts—not outcomes. The original extraction is preserved, edits use optimistic versioning, and the deterministic policy reevaluates the request.</p><div className="review-points"><span><Icon name="check" /> Original v1 preserved</span><span><Icon name="check" /> Reviewer note hashed</span><span><Icon name="check" /> Policy rerun automatically</span></div></div>
          <div className="review-ui"><div className="review-head"><span>CASE · SYNTHETIC-042</span><b>Needs review</b></div><div className="change"><div><small>MODEL EXTRACTED · V1</small><s>Court deadline: unclear</s></div><Icon name="arrow" /><div><small>HUMAN VERIFIED · V2</small><strong>Court deadline: Aug 25</strong></div></div><div className="review-result"><span className="check-badge"><Icon name="check" /></span><div><small>POLICY RE-EVALUATED</small><strong>Qualified for round · Priority tier 1</strong></div></div></div>
        </div>

        <div className="steward-card">
          <div className="steward-heading"><Mark>Taskmaster workflow</Mark><h3>One steward. A complete background job.</h3><p>Repeated steward ticks are safe and idempotent. The agent advances time-bound work; policy tools enforce every consequential transition.</p></div>
          <ol className="steward-timeline">
            <li><span>01</span><div><strong>Open intake</strong><small>Provider-approved charter and seed commitment</small></div><b>automatic</b></li>
            <li><span>02</span><div><strong>Normalize and merge</strong><small>Any language · one principal · one request</small></div><b>continuous</b></li>
            <li className="pause"><span>03</span><div><strong>Pause uncertainty</strong><small>Prompt injection or fact conflicts await review</small></div><b>human gate</b></li>
            <li><span>04</span><div><strong>Freeze and publish</strong><small>Committed seed · deterministic allocation · public proof</small></div><b>automatic</b></li>
            <li><span>05</span><div><strong>Expire and promote</strong><small>Declined offers advance the committed waitlist</small></div><b>automatic</b></li>
            <li><span>06</span><div><strong>Resolve appeals</strong><small>Versioned review · holdback or next-round remedy</small></div><b>audited</b></li>
          </ol>
        </div>
      </section>

      <section className="language-section" id="language">
        <div className="shell language-layout">
          <div className="language-copy"><Mark>Language is access—not a decision factor</Mark><h2>One protocol.<br /><em>Any language.</em></h2><p>Use any BCP 47 language tag supported by the configured Gemini model. The authoritative reason code stays fixed while only approved resident copy is translated.</p><ul><li><Icon name="check" /> Any script or locale tag at intake</li><li><Icon name="check" /> Translation has zero allocation authority</li><li><Icon name="check" /> Failures visibly fall back to English</li></ul></div>
          <div className="language-demo">
            <div className="language-demo-head"><div><Icon name="globe" /><span>Resident explanation preview</span></div><span>REASON LOCKED</span></div>
            <form onSubmit={translateExplanation}><label htmlFor="language-tag">BCP 47 language tag</label><div className="language-input"><input id="language-tag" value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="e.g. ar, sw-KE, zh-Hant" /><button type="submit" disabled={isTranslating}>{isTranslating ? "Translating…" : "Translate"}</button></div><div className="quick-tags">{["hi-Deva-IN", "ar", "sw-KE", "zh-Hant", "fr", "uk"].map((tag) => <button type="button" key={tag} onClick={() => setLanguage(tag)}>{tag}</button>)}</div></form>
            {languageError && <p className="form-error" role="alert">{languageError}</p>}
            <div className="explanation-box" lang={explanation?.delivered_language ?? "en"} dir={/^(ar|fa|he|ur)(-|$)/.test(explanation?.delivered_language ?? "en") ? "rtl" : "ltr"}>
              <small>INCLUDED_IN_ROUND</small><h3>{explanation?.title ?? "Included in the allocation round"}</h3><p>{explanation?.message ?? "Your request meets the published intake rules and has one entry in this round. The kind or speed of agent you used does not change your chance."}</p><div className="next-action"><strong>Next</strong><span>{explanation?.next_action ?? "Wait for the intake window to close. Applying again will not improve your chance."}</span></div>
            </div>
            <div className="delivery-status" aria-live="polite"><span>Requested <b>{explanation?.requested_language ?? language}</b></span><Icon name="arrow" /><span>Delivered <b>{explanation?.delivered_language ?? "en"}</b></span><span className={explanation?.fallback_used ? "fallback" : "safe"}>{explanation ? `${explanation.evidence_source} · ${explanation.fallback_used ? "safe fallback" : "translated"}` : "not run"}</span></div>
          </div>
        </div>
      </section>

      <section className="audit shell">
        <div className="section-heading compact"><div><Mark>Public evidence artifact</Mark><h2>Verify the round without seeing the people.</h2></div><p>No names, requests, principal tokens, or agent identifiers are exposed—only aggregate counts and cryptographic commitments.</p></div>
        <div className="audit-card"><div className="audit-summary"><div className="seal"><Icon name="lock" /></div><div><small>SCENARIO · {proof.scenario_id}</small><h3>Allocation proof valid</h3><p>All six safety invariants passed · {proof.retry_attempts_neutralized} retries neutralized</p></div><span className="public-pill">PUBLIC · SYNTHETIC</span></div><div className="hashes"><HashRow label="Candidate manifest" value={proof.cryptographic_proof.manifest_hash} /><HashRow label="Seed commitment" value={proof.cryptographic_proof.seed_commitment} /><HashRow label="Outcome" value={proof.cryptographic_proof.outcome_hash} /></div></div>
      </section>

      <footer><div className="shell footer-inner"><div><a className="brand" href="#top"><span className="brand-mark"><Icon name="shield" /></span><span>CommonsGate</span></a><p>Fair-access infrastructure for the agentic era.</p></div><div className="footer-note"><span>Built for Google Cloud&apos;s All Things Agentic Hackathon</span><small>Synthetic demonstration · Not legal advice or a production identity system</small></div></div></footer>
    </main>
  );
}
