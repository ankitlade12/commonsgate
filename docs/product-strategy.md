# CommonsGate: product and engineering assessment

## Staff-level verdict

The idea is strong, timely, and more original than a typical hackathon agent. Its
best insight is not “use agents to book services”; it is the invariant that a
person's chance must not change when only their representing agent changes.

The main threat is not feasibility. It is narrative dilution. The PRD currently
contains enough scope for a multi-quarter product: identity, an agent fleet,
policy authoring, simulation, review, appeals, notifications, observability, and
five storage domains. Building a thin version of every component would make the
project look like a queue UI decorated with infrastructure. The submission should
instead prove one new primitive end to end.

## The differentiated product primitive

CommonsGate should be positioned as an **agent-neutral allocation gateway**, not
as a legal-aid app and not as a generic fairness platform. The legal-aid clinic is
the proof domain.

Its defensible bundle is:

1. An agent-blind candidate manifest: transport metadata is retained for audit but
   cryptographically excluded from allocation inputs.
2. Principal-scoped opportunity budgets: one human gets one chance even through
   multiple delegates and retries.
3. Counterfactual replay: run the same represented person through manual, free,
   standard, and premium agent behaviors and prove the decision is identical.
4. Community policy as an allowlisted DSL: AI may draft it, but cannot invent or
   activate criteria.
5. Commit-and-reveal allocation artifacts: policy, candidate manifest, seed
   commitment, revealed seed, and outcome hash form a reproducible proof bundle.

Any one of these can be copied. The integrated evidence loop is the differentiation.

## Critical changes to the PRD

### 1. Separate three fairness claims

- **Exact engineering invariant:** arrival order, retry count, delegate count, and
  agent tier are absent from allocation inputs. This is testable and should be 100%.
- **Statistical group evidence:** allocation rates across experimental agent tiers
  converge across repeated synthetic rounds. This needs intervals and sample sizes.
- **Normative policy fairness:** urgency tiers and reservations are legitimate.
  Software cannot prove this; community governance, simulation, and appeal support it.

The current AAI blends the first two. A small 200-person random demo can exceed an
AAI threshold purely by chance. Report exact paired counterfactual invariance for
the engineering claim, and use 10,000+ cases/repeated seeds for group AAI.

### 2. Define the identity trust boundary honestly

Principal-level deduplication is only as good as the issuer that maps a person to a
scoped token. CommonsGate should not claim to solve Sybil resistance. The MVP uses
a synthetic trusted issuer and demonstrates scoped pseudonymity, collision review,
expiry, audience restriction, and revocation. This is a protocol seam, not a
production identity system.

### 3. Distinguish the frozen intake manifest from the allocation manifest

The audit manifest may include request IDs, agents, retries, and timing. The
allocation manifest must contain only pseudonymous principal tokens and validated
policy facts. Otherwise agent behavior can leak into seed derivation and violate
the central promise indirectly.

### 4. Narrow the autonomous agent story

The most credible autonomy is a long-running intake steward:

- monitors the intake window;
- validates delegated scope;
- normalizes submissions;
- asks once for missing facts;
- routes uncertainty to a human;
- freezes the round at the deadline;
- invokes the deterministic allocator;
- publishes offers and audit artifacts;
- resumes after confirmation, expiry, or appeal.

This is genuine asynchronous action without pretending the LLM should make a
high-stakes allocation decision.

### 5. Do not make Memory Bank the case database

Case state, policy facts, consent, and allocation artifacts belong in typed,
versioned operational storage. Agent memory can retain interaction preferences
such as language and channel, with explicit scope and TTL. Mixing authoritative
case facts into generative memory weakens replay and creates correction problems.

### 6. Make reservation semantics explicit

For every reservation define eligibility, priority interaction, whether unused
capacity releases, and how waitlist promotion works. “Fill reservations” is not
enough to reproduce an outcome. The MVP implements a fixed accommodation reserve,
priority-first selection, and optional release to the general pool.

### 7. Give successful appeals a real remedy

An appeal is performative if every slot is already confirmed. The provider must
publish a remedy policy before opening a round: hold one or two review slots,
fund overflow intake, guarantee the next equivalent slot, or compensate through
another provider. The system should never quietly displace a confirmed resident.

### 8. Treat policy facts as an attack surface

Once speed and retries stop working, sophisticated agents will optimize whatever
facts remain: accommodation flags, urgency dates, evidence formats, and identity
collisions. Add per-field provenance, conflict detection, issuer metadata, and
post-round gaming analysis. Do not turn this into opaque fraud scoring; suspicious
or inconsistent facts go to a human and never become a secret allocation penalty.

### 9. Define late and unavailable-channel policy

A hard window can reproduce the exclusion it is intended to fix. Publish grace
rules for service outages and accessibility barriers, provide phone/caseworker
entry into the same envelope, and use repeated rolling windows when the service's
urgency permits. Never let an administrator quietly insert a late request into a
frozen manifest; use a signed exception or the next round.

### 10. Pre-register the evaluation

Freeze the synthetic generator version, hypotheses, seeds or seed-generation
method, group suppression threshold, and failure gates before final evaluation.
Publish negative controls and all ablations. Otherwise a polished fairness chart
can look cherry-picked even when the allocator is sound.

## Product wedge and moat

The first sellable unit should be a shadow-mode **fairness gateway and audit
report** that sits before an existing scheduler. A provider can replay recent or
synthetic demand without changing live outcomes, compare its current process with
a proposed charter, and obtain an integration plan. This lowers adoption risk and
does not ask staff to replace their case-management system on day one.

The buyer is the provider or scheduling-platform operator, never the resident.
Residents and delegate agents must not be able to buy priority.

The durable moat is not a secret shuffle algorithm. It is the combination of an
interoperable envelope, integrations with scheduler and identity issuers, a corpus
of agent-mediated access attacks, policy-simulation evidence, community governance
workflows, and a trusted audit history across programs.

## Hackathon track decision

Submit as **Taskmaster**. The Round Steward now advances the full asynchronous
workflow: open intake, normalize and deduplicate requests, pause for human review,
freeze the agent-blind manifest, publish deterministic results, expire offers,
promote the waitlist, and record appeal remedies. This maps directly to the
operational-utility criterion without claiming unavailable enterprise services.

Do not submit as Fortified Enterprise Fleet unless the build later demonstrates
every required Registry, Runtime/Memory Bank, Identity/Gateway, Model Armor, and
observability component in the actual account. Product fit or architecture slides
alone are insufficient.

## Winning four-minute demo

1. **Problem (20 seconds):** 200 people, 20 appointments, one premium agent.
2. **Failure (35 seconds):** animate attempts racing into FIFO; premium agents and
   duplicate delegates consume the queue.
3. **Invariant (20 seconds):** swap one resident from manual to premium; show the
   allocation candidate bytes and hash remain identical.
4. **Autonomous workflow (80 seconds):** a synthetic notice in a non-English
   language enters via ADK; Gemini extracts source-linked facts; low confidence
   pauses for human review; a second delegate is merged; the resident selects any
   BCP 47 response language without changing the allocation envelope.
5. **Allocation proof (45 seconds):** close window, reveal committed seed, allocate,
   replay to the same outcome hash.
6. **Evidence and safety (40 seconds):** show baseline AAI, paired change rate of
   zero, blocked cross-principal mutation, and reason-coded appeal.
7. **Cloud proof and close (20 seconds):** live runtime/trace and the one-line promise.

## Build order and gates

### Milestone 1 — fairness proof (implemented)

- Canonical manifest, allocator, schemas, simulator, replay hashes, tests.
- Gate: capacity, uniqueness, retry invariance, order invariance, conflict review,
  and counterfactual representation invariance pass.

### Milestone 2 — complete agentic workflow (implemented locally)

- ADK Round Steward with Gemini 3.5 Flash structured extraction and an idempotent
  lifecycle tool whose seed and credentials remain outside model arguments.
- Confidence/provenance contract and prompt-injection test.
- FastAPI endpoints for request, status, steward transition, offer decision,
  waitlist promotion, appeal remedy, shadow audit, threat evidence, and replay.
- Gate: a synthetic notice reaches either a validated FAE or human review; no model
  output can call allocation without deterministic validation.

### Milestone 3 — visual proof (implemented and browser-verified)

- One Next.js page with interactive FIFO versus CommonsGate allocation rates,
  invariant results, reviewer correction trace, language preview, and replay hashes.
- Public `/v1/demo/proof` and `/v1/rounds/{round_id}/proof` artifacts expose
  aggregate evidence without principal or agent identifiers.
- Gate verified locally: production build, strict typecheck, full-page browser
  render, interactive mode switch, language fallback, and no framework overlay.

## Implemented proof surfaces

| Surface | What it proves | Privacy boundary |
|---|---|---|
| Interactive dashboard | FIFO AAI `0.40` versus CommonsGate AAI `0.04`; individual manual-to-premium sensitivity `90%` versus `0%` | Uses the synthetic 200-person pre-registered scenario |
| Demo proof API | 650 attempts, 450 retries neutralized, six executable invariants, manifest/seed/outcome hashes | Synthetic aggregate only |
| Published-round proof API | Capacity and population counts plus seed reveal and deterministic replay result | Omits request, principal, and agent identifiers |
| Reviewer correction API | Original extraction retained, version incremented, reviewer note hashed, policy reapplied | Raw reviewer note is not written to the audit chain |
| Explanation API | Requested versus delivered BCP 47 tag, model identity, reason-code lock, explicit fallback | Receives approved reason text only; never resident evidence |

### Milestone 4 — cloud execution evidence

- Deploy API/agent/web plus the one-shot steward job to Google Cloud; use
  Firestore for authoritative state, Cloud Scheduler for background invocation,
  and Cloud Logging/Trace for correlation. Add only platform components the team
  can actually demonstrate.
- Gate: a clean, unedited scheduled path is visible on a cloud URL and trace;
  duplicate delivery becomes a lease conflict or idempotent no-op.

### Milestone 5 — evaluation and submission

- Repeated-seed report, counterfactual matrix, threat tests, accessibility check,
  architecture diagram, setup rehearsal, video, and limitations.
- Gate: every statement in Devpost maps to code, a test, a live screen, or a cited
  design limitation.

## Product validation questions that can change the design

Ask legal-aid intake staff and community advocates:

- Is the scarce unit truly an appointment, or is it a call-back/intake review?
- Which urgency facts are reliable before staff contact?
- Would a 30–60 minute intake window harm people with imminent deadlines?
- How are phone, walk-in, accessibility, and caseworker channels reconciled today?
- What duplicate/collision errors occur, and what remedy is acceptable?
- Is random selection within equal-priority cases understandable and legitimate?
- What appeal remedy is possible when all appointments are already confirmed?

If practitioners reject random allocation or the intake-window model, do not paper
over it. Switch the proof domain to a lower-sensitivity scheduled service such as
tax-preparation appointments while preserving the protocol thesis.
