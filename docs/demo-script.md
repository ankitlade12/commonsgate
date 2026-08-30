# Four-minute Taskmaster demo script

Every visual must come from the hosted build. Keep the recording under 3:50 to
leave margin. Use synthetic data only.

## 0:00–0:25 — the friction

Show the dashboard hero and FIFO mode.

> Two hundred equally situated people need twenty legal-aid intake appointments.
> A premium agent can monitor continuously and retry eight times. In a normal
> first-come queue, the agent—not the person—determines access.

Point to the overall FIFO agent-tier spread of `0.40` and the premium cohort
result. Do not present this small-sample descriptive metric as a causal fairness
proof.

## 0:25–0:55 — the invariant

Switch to CommonsGate and rerun the deterministic proof.

> CommonsGate gives one opportunity to the represented person. Agent price,
> latency, retry count, verbosity and language never enter the allocation
> manifest. Changing only the agent changes zero individual outcomes.

Show 650 attempts → 450 neutralized retries → 200 people → 20 offers.

## 0:55–1:45 — unedited autonomous happy path

Show the Cloud Scheduler execution, Cloud Run Job attempt, ADK session and API
logs together. Start with an already-due synthetic round; do not click a manual
"advance" control.

1. Show a clean delegated synthetic non-English request with source-linked Gemini
   extraction in an already-due round.
2. Let Scheduler invoke the job without clicking an advance control.
3. Show `ROUND_FROZEN` and `ALLOCATION_PUBLISHED`, then connect its correlation ID
   across the Cloud Run Job, API logs, and Firestore round.

Say:

> Gemini transforms messy language into quoted, typed facts. It has no decision
> authority. The steward completes the background workflow, while deterministic
> tools control every consequential transition.

## 1:45–2:10 — the safety exception

Show a separate synthetic prompt-injection request. Run its steward tick and show
`paused_for_review=true`; do not resolve it during this segment.

> Autonomy is the normal path, not permission to guess. A flagged request pauses
> with a reason code and versioned review task instead of becoming a silent denial
> or an unsafe allocation.

## 2:10–2:45 — completion, not just selection

Advance time beyond one synthetic offer deadline. Show `OFFER_EXPIRED` followed
by `WAITLIST_PROMOTED`. File and resolve one synthetic appeal using the holdback.

> The job continues after allocation. Expired offers promote the original
> committed waitlist. Appeals preserve the first outcome and append a separately
> hashed remedy record.

## 2:45–3:20 — buyer and security proof

Run Shadow Audit and Run 6 Attacks.

> A provider can begin in shadow mode without replacing its scheduler. Across ten
> seeds, we report small-sample variation honestly; the exact agent-switch change remains
> zero. Retry floods, agent switching, capacity overruns, seed substitution,
> outcome tampering and language leakage are executable checks, not slide claims.

## 3:20–3:45 — cloud and close

Show the `.run.app` URL, Cloud Run revision, Vertex model trace and Firestore
round document. End on the public proof hashes.

> Cloud waiting rooms protect the site. CommonsGate protects the person's chance.
> Same person, same facts, same opportunity—regardless of agent.

## Required honesty line

The hackathon build uses synthetic identities and data. It allocates intake
opportunities, not legal representation, benefits, housing, healthcare or
emergency services. A production deployment requires an approved identity issuer,
provider governance, privacy review and durable audit infrastructure.
