# Devpost submission draft

## CommonsGate — same person, same chance, regardless of agent

**Category:** Taskmaster

CommonsGate is an agent-neutral access gateway for scarce community-service
appointments. It lets providers accept legitimate AI delegates without allowing
faster models, paid agents, repeated submissions, persuasive wording or language
to become priority.

## The friction

When AI agents compete for a fixed number of appointments, people with premium,
always-on agents can submit earlier and more often. Conventional waiting rooms
protect infrastructure and manage visitors; they do not prove that the same human
has the same opportunity across different delegated agents.

## What it does

The ADK Round Steward completes the intake-to-proof workflow:

1. Retrieves a provider's published rules.
2. Uses Gemini 3.5 to extract only explicitly stated facts with source quotes and
   confidence.
3. Merges multiple delegates and retries into one pseudonymous principal request.
4. Pauses conflicts, missing facts and prompt-injection signals for versioned human
   review.
5. Freezes an agent-blind manifest and invokes deterministic policy plus a
   precommitted tie-break.
6. Publishes privacy-safe replay hashes and reason-coded explanations in any
   requested BCP 47 language, with an explicit approved-English fallback.
7. Runs from Cloud Scheduler through a retryable one-shot Cloud Run Job, expires
   unanswered offers, promotes the deterministic waitlist and appends
   appeal remedies to a separate hash ledger.

Gemini never receives an allocation tool and never assigns priority or a slot.
The steward can advance workflow, but its tool cannot supply policy, capacity, a
seed, a winning principal or a review bypass.

## Proof, not promises

The synthetic demonstration sends 650 attempts from 200 people competing for 20
appointments. A naive FIFO queue produces an Agent Advantage Index of `0.40` and
changes outcomes when a person switches to a premium agent. CommonsGate
neutralizes 450 retries and produces an exact `0%` counterfactual outcome change
when only the representing agent changes.

The dashboard includes:

- FIFO versus CommonsGate visual comparison
- Multi-seed shadow audit with P10/P90 sampling range
- Downloadable agent-swap certificate with four independently replayed outcome hashes
- Six executable adversarial checks
- Human-review pause and immutable correction trace
- Any-language BCP 47 explanation preview with explicit English fallback
- Public manifest, seed and outcome commitments

## Google technology

- Gemini 3.5 Flash through Vertex AI for schema-constrained intake extraction and
  approved-copy translation
- Google Agent Development Kit 2.x for the autonomous Round Steward
- Cloud Run for independently permissioned web, agent and API services
- Cloud Scheduler and a one-shot Cloud Run Job for durable background progress
- Firestore for authoritative round, request and appeal state
- Secret Manager for deployment credentials
- Cloud Logging and Cloud Trace for redacted execution evidence

Only services demonstrated in the submitted video should remain in the final list.

## Safety and limitations

The hackathon build uses synthetic identities and data. It allocates intake
opportunities, not legal representation, benefits, housing, healthcare or
emergency services. The HMAC identity issuer is a protocol simulator, not
production proof of personhood or Sybil resistance. Production use requires an
approved issuer, provider governance, privacy/accessibility review, durable audit
storage, recovery procedures and jurisdiction-specific legal review.

## Setup and evidence

- Hosted dashboard: <https://commonsgate-web-c32w4tw36q-uc.a.run.app>
- Public live-round proof: <https://commonsgate-api-c32w4tw36q-uc.a.run.app/v1/rounds/round-demo/proof>
- Downloadable agent-swap certificate: <https://commonsgate-web-c32w4tw36q-uc.a.run.app/api/agent-swap-certificate>
- Reproducible setup: repository `README.md`
- Architecture and boundaries: `docs/architecture.md`
- Standalone architecture upload: `docs/architecture-upload.png`
- Deployment: `docs/cloud-deployment.md`
- Four-minute recording plan: `docs/demo-script.md`
- Automated checks: backend, property, adversarial, API lifecycle, TypeScript and
  production Next.js build

## Required owner-supplied submission fields

- **Hosted URL:** `https://commonsgate-web-c32w4tw36q-uc.a.run.app` (verified with
  live API evidence and backend revision `commonsgate-api-00007-wm2`).
- **Public repository:** verify anonymous access, or invite both hackathon testing
  accounts named in the Devpost rules before submission.
- **Video:** public YouTube or Vimeo URL, at most four minutes, with English audio
  or subtitles.
- **Build period:** enter the truthful project start date and identify any
  pre-existing components.
- **Bring-your-own-friction story:** add the founder's authentic first-person
  reason for caring about agent-mediated access. Do not replace this with invented
  user research or endorsements.
- **Google Cloud evidence:** deployment is verified in project
  `commonsgate-ankit-2026`; capture the real service revisions, Scheduler
  execution, Vertex model call, Firestore document, and redacted correlation trace
  in the video.
