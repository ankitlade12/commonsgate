# Remaining work, ordered by submission risk

The winning-path product loop is implemented locally: an ADK Round Steward can
advance an idempotent lifecycle; review pauses are enforced; offers expire;
waitlists promote deterministically; appeals create auditable remedies; and the
dashboard exposes a multi-seed shadow audit plus executable threat evidence.

## P0 — external proof required before submission

1. **Authenticate Google Cloud and deploy all three services.** Build and deploy
   `commonsgate-api`, `commonsgate-agent`, and `commonsgate-web`; record exact
   revisions and URLs. No successful cloud deployment is claimed yet.
2. **Verify the live Gemini 3.5 path.** Run multilingual structured extraction and
   non-English reason translation through Vertex AI. Capture model ID, structured
   output, explicit fallback behavior, latency, and a redacted trace.
3. **Verify the live ADK workflow.** Show the steward opening the round, submitting
   a delegated request, pausing a flagged case, resuming after correction,
   publishing, and producing proof. Confirm that no model tool can provide a seed,
   capacity, policy, principal winner, or review-bypass argument.
4. **Verify Firestore durability and concurrency.** Restart a service instance,
   prove state survives, race principal submissions and reviewer/appeal versions,
   and validate the new appeal collection queries against the emulator or live
   database.
5. **Add cloud observability evidence.** Propagate one correlation ID across web,
   ADK, API, Gemini and Firestore; show Cloud Logging/Trace without raw intake text,
   principal tokens, delegation tokens, or secrets.
6. **Record the four-minute video.** Follow `docs/demo-script.md`. The video must
   show an unedited live action, the Google Cloud backend, and only verified claims.
7. **Publish the repository.** Commit the current work, push it to an accessible
   repository, verify clean setup from a fresh clone, and add the hosted URL.

## P1 — validation that improves operational utility

1. Conduct two or three short interviews with legal-aid/community intake staff.
   Record workflow facts and objections, not invented endorsements. Use
   `docs/provider-interview-guide.md`.
2. Replace the synthetic HMAC issuer with an approved asymmetric issuer and
   revocation path. CommonsGate consumes identity assurance; it does not solve
   universal Sybil resistance.
3. Persist the audit chain and idempotency/replay records in durable transactional
   storage. The current audit and nonce adapters remain process-local.
4. Add reviewed terminology packs and language quality sampling. Arbitrary BCP 47
   support is an open mechanism, not a promise that every translation is correct.

## Explicitly deferred

- Full resident/provider/reviewer application suites
- Multi-provider matching and overflow exchanges
- Model-authored allocation policy
- Real patient, client, housing, benefits, or emergency-service data
- Fortified Enterprise Fleet claims without every required service demonstrated

