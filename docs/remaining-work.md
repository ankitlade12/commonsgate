# Remaining work, ordered by submission risk

The winning-path product loop is implemented locally: an ADK Round Steward can
advance an idempotent lifecycle; review pauses are enforced; offers expire;
waitlists promote deterministically; appeals create auditable remedies; and the
dashboard exposes a multi-seed shadow audit plus executable threat evidence. A
one-shot Cloud Run Job and Cloud Scheduler configuration now provide real
background invocation. CI, dependency audits, durable Firestore audit/nonce/
idempotency records, a distributed steward lease, security headers, honest
live-versus-offline evidence labels, and a standalone architecture upload are in
the repository.

## P0 — external proof required before submission

1. **Confirm the target Google Cloud project, then deploy.** Build and deploy
   `commonsgate-api`, `commonsgate-agent`, `commonsgate-web`, and the
   `commonsgate-scheduler` job; enable its Scheduler trigger and record exact
   revisions and URLs. The currently configured project is ambiguous, so no cloud
   mutation or successful deployment is claimed yet.
2. **Verify the live Gemini 3.5 path.** Run multilingual structured extraction and
   non-English reason translation through Vertex AI. Capture model ID, structured
   output, explicit fallback behavior, latency, and a redacted trace.
3. **Verify the live ADK workflow.** Show the steward opening the round, submitting
   a delegated request, pausing a flagged case, resuming after correction,
   publishing, and producing proof. Confirm that no model tool can provide a seed,
   capacity, policy, principal winner, or review-bypass argument.
4. **Verify Firestore durability and duplicate delivery.** Restart a service
   instance, prove state/audit/nonce/idempotency survive, race two scheduled ticks,
   and validate appeal queries against the emulator or live database.
5. **Add cloud observability evidence.** Propagate one correlation ID across web,
   ADK, API, Gemini and Firestore; show Cloud Logging/Trace without raw intake text,
   principal tokens, delegation tokens, or secrets.
6. **Record the four-minute video.** Follow `docs/demo-script.md`. The video must
   show an unedited live action, the Google Cloud backend, and only verified claims.
7. **Make submission access explicit.** The Git remote is
   `ankitlade12/commonsgate`; after this branch is merged, verify anonymous clone
   access or invite the two Devpost testing accounts, verify clean setup from a
   fresh clone, and add the hosted URL.
8. **Supply the human-only fields.** Add an authentic first-person friction story,
   truthful project start date, public four-minute video URL, and final team/member
   details. These cannot be responsibly fabricated by the implementation.

## P1 — validation that improves operational utility

1. Conduct two or three short interviews with legal-aid/community intake staff.
   Record workflow facts and objections, not invented endorsements. Use
   `docs/provider-interview-guide.md`.
2. Replace the synthetic HMAC issuer with an approved asymmetric issuer and
   revocation path. CommonsGate consumes identity assurance; it does not solve
   universal Sybil resistance.
3. Add end-to-end Firestore transaction/CAS coverage for every cross-document
   request/review/appeal mutation; current version checks and steward lease protect
   the demonstrated path, but do not make every multi-document operation atomic.
4. Add reviewed terminology packs and language quality sampling. Arbitrary BCP 47
   support is an open mechanism, not a promise that every translation is correct.

## Explicitly deferred

- Full resident/provider/reviewer application suites
- Multi-provider matching and overflow exchanges
- Model-authored allocation policy
- Real patient, client, housing, benefits, or emergency-service data
- Fortified Enterprise Fleet claims without every required service demonstrated
