# Cloud deployment runbook

The deployable architecture uses three independently permissioned Cloud Run
services:

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

This separation makes the security boundary visible in IAM and in the demo.

## Prerequisites

- An authenticated `gcloud` account with the target project selected
- Billing enabled
- Cloud Run, Cloud Build, Artifact Registry, Firestore, Secret Manager, Vertex
  AI, Cloud Logging, and Cloud Trace APIs enabled
- A Firestore database in Native mode
- Two service accounts: one for the API and one for the agent

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
```

## Deploy the API

```bash
gcloud run deploy commonsgate-api \
  --image REGION-docker.pkg.dev/PROJECT_ID/commonsgate/api:VERSION \
  --region REGION \
  --service-account commonsgate-api@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars COMMONSGATE_ENV=production,COMMONSGATE_NORMALIZER=gemini,COMMONSGATE_TRANSLATOR=gemini,COMMONSGATE_REPOSITORY=firestore,COMMONSGATE_ENABLE_CLOUD_TRACE=true,COMMONSGATE_GEMINI_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=REGION \
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
  --set-env-vars COMMONSGATE_API_URL=https://API_URL,COMMONSGATE_ADK_MODEL=gemini-3.5-flash,COMMONSGATE_DEMO_AGENT_ID=demo-free-agent,COMMONSGATE_DEMO_PRINCIPAL_TOKEN=synthetic-principal-token-0001,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=REGION \
  --update-secrets COMMONSGATE_DEMO_DELEGATION_TOKEN=commonsgate-demo-delegation:latest,COMMONSGATE_ADMIN_KEY=commonsgate-admin-key:latest,COMMONSGATE_DEMO_ROUND_SEED=commonsgate-demo-round-seed:latest \
  --no-allow-unauthenticated
```

## Verification gates

- `/healthz` reports `GeminiNormalizer`, `FirestoreRepository`, and a valid audit
  chain.
- The ADK server exposes an A2A agent card and accepts an authenticated run.
- A synthetic intake request reaches `QUALIFIED_FOR_ROUND` or
  `PENDING_HUMAN_REVIEW` with field provenance.
- A prompt-injection case is routed to review.
- The agent cannot call raw close/allocation endpoints or supply policy, capacity,
  seed, or winner arguments; its steward call pauses while review is pending.
- Closing and replaying a round returns identical manifest and outcome hashes.
- `/v1/demo/proof` and the dashboard show the same metrics and commitments.
- A non-English BCP 47 explanation either returns a Gemini translation or visibly
  reports the approved English fallback; the reason code remains unchanged.
- Cloud Logging contains correlation IDs but no raw intake text or delegation
  tokens.

## Current external blocker

An active `gcloud` account is present, but the configured project is
`caseproof-xprize-ankit-2026`, which does not clearly identify this product, and
Cloud Resource Manager is not enabled there. Do not mutate or deploy into that
project until the owner explicitly confirms it as the CommonsGate target or
provides a different project ID. Actual service names, URLs, trace screenshots,
and deployed revisions must be recorded only after deployment succeeds.
