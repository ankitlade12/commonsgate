# Cloud deployment runbook

The deployable architecture uses three independently permissioned Cloud Run
services plus one one-shot Cloud Run Job:

1. `commonsgate-api` owns authoritative request and round state in Firestore. It
   calls Gemini for extraction but never gives the model allocation tools.
2. `commonsgate-agent` is the ADK/A2A Round Steward. It can read the public
   program, submit for its delegated synthetic principal, read that principal's
   status, and invoke one provider-approved, idempotent steward operation. The
   adapter holds the seed and credential; it cannot alter policy, choose a seed,
   name a winner, or bypass review.
3. `commonsgate-web` is the public proof dashboard. It calls only the public proof
   and reason-template routes through server-side handlers; provider administration
    remains outside the public browser bundle.
4. `commonsgate-scheduler` is a non-public Cloud Run Job invoked by Cloud
   Scheduler. It calls one bounded steward tick for a configured round. The seed
   and credential are server-held, and duplicate delivery is guarded by a durable
   lease plus idempotent transitions.

This separation makes the security boundary visible in IAM and in the demo.

## Prerequisites

- An authenticated `gcloud` account with the target project selected
- Billing enabled
- Cloud Run, Cloud Build, Artifact Registry, Firestore, Secret Manager, Vertex
  AI, Cloud Logging, and Cloud Trace APIs enabled
- A Firestore database in Native mode
- Separate least-privilege service accounts for the API, agent, scheduler job,
  and Scheduler invoker

Do not grant the agent service account direct Firestore write access. The agent
must pass through the API authorization and audit boundary.

## Required secrets

- `commonsgate-delegation-secret`: at least 32 random bytes
- `commonsgate-admin-key`: random provider-administration credential for the demo
- `commonsgate-demo-delegation`: scoped synthetic delegation used by the ADK demo
- `commonsgate-demo-round-seed`: seed matching the round's prepublished commitment

Use Secret Manager references on Cloud Run. Do not put their values in command
history, deployment YAML, screenshots, or the repository.

## Build images

Replace the project, region, and repository placeholders before running:

```bash
gcloud builds submit \
  --config infrastructure/cloudbuild-api.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT_ID/commonsgate/api:VERSION .

gcloud builds submit \
  --config infrastructure/cloudbuild-agent.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT_ID/commonsgate/agent:VERSION .

gcloud builds submit \
  --config infrastructure/cloudbuild-web.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT_ID/commonsgate/web:VERSION .

gcloud builds submit \
  --config infrastructure/cloudbuild-scheduler.yaml \
  --substitutions _IMAGE=REGION-docker.pkg.dev/PROJECT_ID/commonsgate/scheduler:VERSION .
```

## Deploy the API

```bash
gcloud run deploy commonsgate-api \
  --image REGION-docker.pkg.dev/PROJECT_ID/commonsgate/api:VERSION \
  --region REGION \
  --service-account commonsgate-api@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars COMMONSGATE_ENV=production,COMMONSGATE_NORMALIZER=gemini,COMMONSGATE_TRANSLATOR=gemini,COMMONSGATE_REPOSITORY=firestore,COMMONSGATE_ENABLE_CLOUD_TRACE=true,COMMONSGATE_GEMINI_MODEL=gemini-3.5-flash,COMMONSGATE_AGENT_A2A_URL=https://AGENT_URL/a2a/commonsgate_agent,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=global \
  --update-secrets COMMONSGATE_DELEGATION_SECRET=commonsgate-delegation-secret:latest,COMMONSGATE_ADMIN_KEY=commonsgate-admin-key:latest \
  --allow-unauthenticated
```

The API is network-public because the proof/schema routes are public and the web
and agent adapters do not yet mint Cloud Run identity tokens. Consequential routes
still require delegation or provider credentials in application code. A production
deployment should split public proof from private command traffic or add
service-to-service OIDC before disabling unauthenticated ingress.

## Deploy the public dashboard

```bash
gcloud run deploy commonsgate-web \
  --image REGION-docker.pkg.dev/PROJECT_ID/commonsgate/web:VERSION \
  --region REGION \
  --set-env-vars COMMONSGATE_API_URL=https://API_URL \
  --allow-unauthenticated
```

The API URL should expose only the intended public program, proof, and approved
explanation-template routes to this service. Administrative and resident-scoped
routes retain their own authentication requirements.

For a public hackathon demo, place an authenticated frontend or Identity-Aware
Proxy in front of the administrative endpoints. Do not make the admin key the
long-term production authorization mechanism.

## Deploy the ADK agent

```bash
gcloud run deploy commonsgate-agent \
  --image REGION-docker.pkg.dev/PROJECT_ID/commonsgate/agent:VERSION \
  --region REGION \
  --service-account commonsgate-agent@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars COMMONSGATE_API_URL=https://API_URL,COMMONSGATE_ADK_MODEL=gemini-3.5-flash,COMMONSGATE_DEMO_AGENT_ID=demo-free-agent,COMMONSGATE_DEMO_PRINCIPAL_TOKEN=synthetic-principal-token-0001,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=global \
  --update-secrets COMMONSGATE_DEMO_DELEGATION_TOKEN=commonsgate-demo-delegation:latest,COMMONSGATE_ADMIN_KEY=commonsgate-admin-key:latest,COMMONSGATE_DEMO_ROUND_SEED=commonsgate-demo-round-seed:latest \
  --no-allow-unauthenticated
```

## Deploy autonomous background execution

Create the target round before enabling the schedule. The round seed secret must
match that round's already-published seed commitment.

```bash
gcloud run jobs deploy commonsgate-scheduler \
  --image REGION-docker.pkg.dev/PROJECT_ID/commonsgate/scheduler:VERSION \
  --region REGION \
  --service-account commonsgate-scheduler@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars COMMONSGATE_API_URL=https://API_URL,COMMONSGATE_ROUND_ID=ROUND_ID \
  --update-secrets COMMONSGATE_ADMIN_KEY=commonsgate-admin-key:latest,COMMONSGATE_DEMO_ROUND_SEED=commonsgate-demo-round-seed:latest \
  --max-retries 3 \
  --task-timeout 120s
```

Grant a dedicated invoker permission on only this job, then create the Scheduler
trigger. Cloud Scheduler may deliver a request more than once; this design treats
that as expected rather than relying on exactly-once delivery.

```bash
gcloud run jobs add-iam-policy-binding commonsgate-scheduler \
  --region REGION \
  --member serviceAccount:commonsgate-scheduler-invoker@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/run.invoker

gcloud scheduler jobs create http commonsgate-steward-every-minute \
  --location REGION \
  --schedule "* * * * *" \
  --uri "https://run.googleapis.com/v2/projects/PROJECT_ID/locations/REGION/jobs/commonsgate-scheduler:run" \
  --http-method POST \
  --oauth-service-account-email commonsgate-scheduler-invoker@PROJECT_ID.iam.gserviceaccount.com
```

For the video, show one Scheduler execution, its Cloud Run Job attempt, and the
matching API correlation ID. Disable or delete the trigger after the synthetic
demo round is complete to avoid idle invocations.

## Verification gates

- `/health` reports `GeminiNormalizer`, `FirestoreRepository`, and a valid audit
  chain.
- The ADK server exposes an A2A agent card and accepts an authenticated run.
- A synthetic intake request reaches `QUALIFIED_FOR_ROUND` or
  `PENDING_HUMAN_REVIEW` with field provenance.
- A prompt-injection case is routed to review.
- The agent cannot call raw close/allocation endpoints or supply policy, capacity,
  seed, or winner arguments; its steward call pauses while review is pending.
- Closing and replaying a round returns identical manifest and outcome hashes.
- A Scheduler-triggered job advances a due round without a human click; concurrent
  duplicate ticks return a lease conflict or no-op and do not double-publish.
- `/v1/demo/proof` and the dashboard show the same metrics and commitments.
- A non-English BCP 47 explanation either returns a Gemini translation or visibly
  reports the approved English fallback; the reason code remains unchanged.
- Cloud Logging contains correlation IDs but no raw intake text or delegation
  tokens.

## Verified deployment — 2026-08-30

- Project: `commonsgate-ankit-2026` (`146601709730`), region `us-central1`
- Dashboard: <https://commonsgate-web-c32w4tw36q-uc.a.run.app>, revision
  `commonsgate-web-00003-nxb`
- API: <https://commonsgate-api-c32w4tw36q-uc.a.run.app>, revision
  `commonsgate-api-00007-wm2`
- Private ADK/A2A service: `commonsgate-agent`, revision
  `commonsgate-agent-00005-fxb`
- Scheduler job: `commonsgate-scheduler`; recurring trigger
  `commonsgate-steward-every-minute` is paused after verification
- Firestore: Native `(default)` database in `nam5`
- Cost guardrail: project-scoped `$30` monthly budget with 50%, 90%, 100%, and
  forecasted-100% alerts

Verified evidence:

- `/health` reports Gemini extraction/translation, `FirestoreRepository`,
  production, Cloud Trace enabled, and a valid audit chain.
- An authenticated ADK run called `get_intake_program`; the A2A card is available
  at `/a2a/commonsgate_agent/.well-known/agent-card.json` to authenticated callers.
- The public API discovery card mirrors the real service's JSON-RPC `0.3.0`
  metadata through `COMMONSGATE_AGENT_A2A_URL`; it does not advertise the REST API
  root as an A2A transport.
- Gemini 3.5 Flash produced a qualified, source-linked intake with application-owned
  schema/prompt/model metadata and `decision_authority=none`.
- A separate Gemini 3.5 Flash call delivered a reason-locked `es-MX` translation
  without changing its reason code.
- Scheduler logged `paused_for_review=true` with three pending reviews. After
  versioned corrections, it logged `ROUND_FROZEN` and `ALLOCATION_PUBLISHED`.
- The public round proof reports 6 candidates, 2 initial allocations, 4 waitlisted,
  a 1-slot appeal holdback, valid audit chain, and verified replay.
- The downloadable agent-swap certificate independently replays manual, free,
  standard, and premium representations. All four produce the same manifest and
  outcome hashes, with a measured maximum outcome change of `0%` and certificate
  hash `b1132393852debf1a94f0b39dc3285725872d30e9c2f87a9d19993c2c69650d8`.
- The public FAE schema exposes only normalized, agent-neutral decision facts and
  deliberately excludes raw text and submission timestamps.
- State created before later API deployments remained available after revision
  `00007`, demonstrating live Firestore persistence across revisions.
- The final dashboard rendered live API evidence, live shadow and threat reports,
  and live `hi-Deva-IN` translation with no browser console or page errors.
