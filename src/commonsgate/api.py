"""FastAPI boundary for the complete intake-to-allocation demo path."""

from __future__ import annotations

import hmac
import time
import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from .audit import AuditLog, FirestoreAuditLog
from .auth import DelegationTokenService
from .contracts import (
    AgentSwapCertificate,
    AppealCreateRequest,
    AppealRecord,
    AppealResolutionRequest,
    DelegationIssueRequest,
    DelegationIssueResponse,
    DemoProofBundle,
    ErrorBody,
    ErrorResponse,
    FairAccessEnvelope,
    IntakeSubmission,
    LocalizedExplanation,
    OfferDecisionRequest,
    RequestReceipt,
    ReviewCorrection,
    RoundCreateRequest,
    RoundPublicProof,
    RoundRecord,
    SeedRevealRequest,
    ShadowAuditReport,
    ShadowAuditRequest,
    StewardTickReport,
    StewardTickRequest,
    StoredRequest,
    ThreatReport,
)
from .errors import CommonsGateError
from .explanations import ExplanationTranslator, build_explanation_translator
from .normalization import Normalizer, build_normalizer
from .observability import (
    TRACER,
    configure_cloud_trace,
    current_span_attributes,
    log_event,
)
from .repository import FirestoreRepository, InMemoryRepository, Repository
from .service import CommonsGateService
from .settings import Settings


def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex}"


def _bearer(authorization: str) -> str:
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        raise CommonsGateError(
            "DELEGATION_INVALID",
            "Authorization must contain a Bearer delegation token.",
            status_code=403,
        )
    return token


def build_service(
    *,
    settings: Settings,
    normalizer: Normalizer | None = None,
    explanation_translator: ExplanationTranslator | None = None,
) -> CommonsGateService:
    repository: Repository
    audit_log: AuditLog
    if settings.repository_mode == "firestore":
        from google.cloud import firestore

        firestore_client = firestore.Client()
        repository = FirestoreRepository(
            client=firestore_client,
            collection_prefix=settings.firestore_collection_prefix,
        )
        audit_log = FirestoreAuditLog(
            client=firestore_client,
            collection_prefix=settings.firestore_collection_prefix,
        )
    else:
        repository = InMemoryRepository()
        audit_log = AuditLog()
    return CommonsGateService(
        repository=repository,
        normalizer=normalizer or build_normalizer(settings.normalizer_mode),
        token_service=DelegationTokenService(settings.delegation_signing_secret),
        audit_log=audit_log,
        explanation_translator=(
            explanation_translator
            or build_explanation_translator(settings.translator_mode)
        ),
    )


def create_app(
    *,
    settings: Settings | None = None,
    normalizer: Normalizer | None = None,
    explanation_translator: ExplanationTranslator | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    trace_enabled = configure_cloud_trace(
        service_name=resolved_settings.service_name,
        enabled=resolved_settings.enable_cloud_trace,
    )
    service = build_service(
        settings=resolved_settings,
        normalizer=normalizer,
        explanation_translator=explanation_translator,
    )
    app = FastAPI(
        title="CommonsGate API",
        version="0.4.0",
        description="Agent-neutral intake, review, explanation, and verifiable deterministic allocation boundary.",
    )
    app.state.service = service
    app.state.settings = resolved_settings

    def require_admin(x_admin_key: str = Header(alias="X-Admin-Key")) -> str:
        if not hmac.compare_digest(x_admin_key, resolved_settings.admin_key):
            raise CommonsGateError(
                "ACTION_NOT_PERMITTED",
                "Provider administrator access is required.",
                status_code=403,
            )
        return "provider-admin"

    @app.middleware("http")
    async def attach_correlation_id(request: Request, call_next: Callable):
        request.state.correlation_id = _correlation_id(request)
        started = time.perf_counter()
        with TRACER.start_as_current_span("commonsgate.http"):
            current_span_attributes(
                correlation_id=request.state.correlation_id,
                method=request.method,
            )
            response = await call_next(request)
            route = getattr(request.scope.get("route"), "path", "unmatched")
            duration_ms = round((time.perf_counter() - started) * 1_000, 2)
            current_span_attributes(route=route, status_code=response.status_code)
            log_event(
                "http_request",
                correlation_id=request.state.correlation_id,
                method=request.method,
                route=route,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response

    @app.exception_handler(CommonsGateError)
    async def commonsgate_error_handler(request: Request, exc: CommonsGateError):
        correlation_id = getattr(
            request.state, "correlation_id", _correlation_id(request)
        )
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                correlation_id=correlation_id,
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return JSONResponse(
            status_code=exc.status_code, content=body.model_dump(mode="json")
        )

    @app.get("/health")
    @app.get("/healthz")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "normalizer": service.normalizer.name,
            "translator": service.explanation_translator.name,
            "repository": type(service.repository).__name__,
            "environment": resolved_settings.environment,
            "service_revision": resolved_settings.service_revision,
            "audit_chain_valid": service.audit_log.verify_chain(),
            "cloud_trace_enabled": trace_enabled,
        }

    @app.get("/.well-known/agent-card.json")
    def agent_card() -> dict[str, object]:
        return {
            "name": "CommonsGate Round Steward",
            "description": "A bounded fair-access steward that normalizes authorized requests and advances a deterministic round without choosing winners.",
            "supportedInterfaces": [
                {
                    "url": resolved_settings.agent_a2a_url,
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "0.3.0",
                }
            ],
            "url": resolved_settings.agent_a2a_url,
            "version": "0.4.0",
            "protocolVersion": "0.3.0",
            "preferredTransport": "JSONRPC",
            "capabilities": {"streaming": True},
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": [
                {
                    "id": "submit_fair_access_request",
                    "name": "Submit fair-access request",
                    "description": "Extract facts, preserve provenance, request missing information, and route ambiguity to human review.",
                    "tags": ["intake", "fair-access", "human-review"],
                },
                {
                    "id": "read_request_status",
                    "name": "Read authorized request status",
                    "description": "Returns reason-coded status for the represented principal only.",
                    "tags": ["status", "delegation"],
                },
                {
                    "id": "read_public_allocation_proof",
                    "name": "Read privacy-safe allocation proof",
                    "description": "Returns aggregate invariants and replay commitments without resident or agent identifiers.",
                    "tags": ["proof", "replay", "privacy"],
                },
                {
                    "id": "explain_reason_code",
                    "name": "Explain an approved reason code",
                    "description": "Translates approved resident copy for a BCP 47 language tag without changing the decision.",
                    "tags": ["language", "explanation", "reason-code"],
                },
                {
                    "id": "advance_round_workflow",
                    "name": "Advance autonomous round workflow",
                    "description": "Opens, pauses for review, freezes, allocates, expires offers, and promotes the deterministic waitlist.",
                    "tags": ["workflow", "taskmaster", "human-review"],
                },
            ],
        }

    @app.get("/v1/programs/{program_id}")
    def get_program(program_id: str) -> dict[str, object]:
        return {
            "program_id": program_id,
            "provider_id": "provider-demo",
            "round_id": "round-demo",
            "service_type": "housing_legal_intake",
            "required_facts": [
                {
                    "field": "service_area_confirmed",
                    "request": "State whether the synthetic matter is in Cook County or Chicago.",
                },
                {
                    "field": "court_deadline_date",
                    "request": "State the explicit court or response deadline as an ISO date.",
                },
                {
                    "field": "accommodation_requested",
                    "request": "State whether an accessibility accommodation is requested.",
                },
            ],
            "optional_facts": [
                {
                    "field": "preferred_language",
                    "request": "Optionally state a preferred communication language.",
                }
            ],
            "not_required": [
                "name",
                "contact_information",
                "income",
                "agent_vendor",
                "agent_subscription_tier",
            ],
            "policy_summary": {
                "service_area": "Cook County",
                "priority": "Published deadline tiers",
                "tie_break": "Committed deterministic randomization within equivalent pools",
                "agent_speed_used": False,
                "retry_count_used": False,
            },
            "human_support_available": True,
            "synthetic_demo_only": True,
        }

    @app.get("/v1/programs/{program_id}/fae-schema")
    def get_fae_schema(program_id: str) -> dict[str, object]:
        schema = FairAccessEnvelope.model_json_schema()
        schema["$id"] = (
            "https://commonsgate.dev/schemas/fair-access-envelope/1.0.0"
        )
        schema["title"] = "Fair Access Envelope"
        schema["x-program-id"] = program_id
        return schema

    @app.get("/v1/demo/proof", response_model=DemoProofBundle)
    def demo_proof_endpoint() -> DemoProofBundle:
        """Public, deterministic, synthetic evidence for the product claim."""

        return service.demo_proof()

    @app.get(
        "/v1/demo/agent-swap-certificate",
        response_model=AgentSwapCertificate,
    )
    def agent_swap_certificate_endpoint() -> AgentSwapCertificate:
        """Publish a content-hashed replay of agent-only counterfactuals."""

        return service.agent_swap_certificate()

    @app.get("/v1/demo/threats", response_model=ThreatReport)
    def threat_report_endpoint() -> ThreatReport:
        """Execute privacy-safe adversarial controls against synthetic traffic."""

        return service.threat_report()

    @app.post("/v1/demo/shadow-audit", response_model=ShadowAuditReport)
    def shadow_audit_endpoint(payload: ShadowAuditRequest) -> ShadowAuditReport:
        """Compare a retry-sensitive queue with CommonsGate across many seeds."""

        return service.shadow_audit(payload)

    @app.get(
        "/v1/explanations/{reason_code}",
        response_model=LocalizedExplanation,
    )
    async def public_explanation_preview_endpoint(
        reason_code: str,
        language: Annotated[
            str,
            Query(
                min_length=2,
                max_length=35,
                pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
            ),
        ] = "en",
    ) -> LocalizedExplanation:
        """Translate approved policy copy without exposing any resident record."""

        return await service.explanation_translator.explain(reason_code, language)

    @app.post("/v1/demo/delegations", response_model=DelegationIssueResponse)
    def issue_demo_delegation(
        payload: DelegationIssueRequest,
        _actor: str = Depends(require_admin),
    ) -> DelegationIssueResponse:
        token, claims = service.token_service.issue(payload)
        return DelegationIssueResponse(
            delegation_id=claims.delegation_id,
            token=token,
            expires_at=claims.expires_at,
        )

    @app.post("/v1/rounds", response_model=RoundRecord, status_code=201)
    def create_round_endpoint(
        payload: RoundCreateRequest,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> RoundRecord:
        return service.create_round(
            payload, actor_id=actor, correlation_id=request.state.correlation_id
        )

    @app.get("/v1/rounds/{round_id}", response_model=RoundRecord)
    def get_round_endpoint(
        round_id: str, _actor: str = Depends(require_admin)
    ) -> RoundRecord:
        return service.repository.get_round(round_id)

    @app.post("/v1/rounds/{round_id}/open", response_model=RoundRecord)
    def open_round_endpoint(
        round_id: str,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> RoundRecord:
        return service.open_round(
            round_id, actor_id=actor, correlation_id=request.state.correlation_id
        )

    @app.post("/v1/rounds/{round_id}/close", response_model=RoundRecord)
    def close_round_endpoint(
        round_id: str,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> RoundRecord:
        return service.close_round(
            round_id, actor_id=actor, correlation_id=request.state.correlation_id
        )

    @app.post("/v1/rounds/{round_id}/allocate", response_model=RoundRecord)
    def allocate_round_endpoint(
        round_id: str,
        payload: SeedRevealRequest,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> RoundRecord:
        return service.allocate_round(
            round_id,
            seed=payload.seed,
            actor_id=actor,
            correlation_id=request.state.correlation_id,
        )

    @app.post(
        "/v1/rounds/{round_id}/steward/tick", response_model=StewardTickReport
    )
    def steward_tick_endpoint(
        round_id: str,
        payload: StewardTickRequest,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> StewardTickReport:
        return service.steward_tick(
            round_id,
            payload,
            actor_id=f"{actor}:round-steward",
            correlation_id=request.state.correlation_id,
        )

    @app.get("/v1/rounds/{round_id}/audit")
    def round_audit_endpoint(
        round_id: str, _actor: str = Depends(require_admin)
    ) -> dict[str, object]:
        return {
            "round_id": round_id,
            "chain_valid": service.audit_log.verify_chain(),
            "events": [
                event.model_dump(mode="json")
                for event in service.audit_log.list_for_object(round_id)
            ],
        }

    @app.get("/v1/rounds/{round_id}/proof", response_model=RoundPublicProof)
    def public_round_proof_endpoint(round_id: str) -> RoundPublicProof:
        return service.public_round_proof(round_id)

    @app.post("/v1/requests", response_model=RequestReceipt, status_code=201)
    async def submit_request_endpoint(
        payload: IntakeSubmission,
        request: Request,
        authorization: str = Header(alias="Authorization"),
        agent_id: str = Header(alias="X-Agent-ID"),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        nonce: str = Header(alias="X-Request-Nonce"),
    ) -> RequestReceipt:
        return await service.submit_request(
            payload,
            token=_bearer(authorization),
            agent_id=agent_id,
            idempotency_key=idempotency_key,
            nonce=nonce,
            correlation_id=request.state.correlation_id,
        )

    @app.get("/v1/requests/{request_id}", response_model=StoredRequest)
    def get_request_endpoint(
        request_id: str,
        request: Request,
        authorization: str = Header(alias="Authorization"),
        agent_id: str = Header(alias="X-Agent-ID"),
    ) -> StoredRequest:
        return service.get_request(
            request_id,
            token=_bearer(authorization),
            agent_id=agent_id,
            correlation_id=request.state.correlation_id,
        )

    @app.get(
        "/v1/requests/{request_id}/explanation",
        response_model=LocalizedExplanation,
    )
    async def explain_request_endpoint(
        request_id: str,
        request: Request,
        language: Annotated[
            str,
            Query(
                min_length=2,
                max_length=35,
                pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
            ),
        ] = "en",
        authorization: str = Header(alias="Authorization"),
        agent_id: str = Header(alias="X-Agent-ID"),
    ) -> LocalizedExplanation:
        return await service.explain_request(
            request_id,
            language_tag=language,
            token=_bearer(authorization),
            agent_id=agent_id,
            correlation_id=request.state.correlation_id,
        )

    @app.post("/v1/requests/{request_id}/review", response_model=StoredRequest)
    def correct_review_endpoint(
        request_id: str,
        payload: ReviewCorrection,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> StoredRequest:
        return service.correct_review(
            request_id,
            payload,
            actor_id=actor,
            correlation_id=request.state.correlation_id,
        )

    @app.post("/v1/requests/{request_id}/offer", response_model=StoredRequest)
    def decide_offer_endpoint(
        request_id: str,
        payload: OfferDecisionRequest,
        request: Request,
        authorization: str = Header(alias="Authorization"),
        agent_id: str = Header(alias="X-Agent-ID"),
    ) -> StoredRequest:
        return service.decide_offer(
            request_id,
            payload,
            token=_bearer(authorization),
            agent_id=agent_id,
            correlation_id=request.state.correlation_id,
        )

    @app.post(
        "/v1/requests/{request_id}/appeals",
        response_model=AppealRecord,
        status_code=201,
    )
    def create_appeal_endpoint(
        request_id: str,
        payload: AppealCreateRequest,
        request: Request,
        authorization: str = Header(alias="Authorization"),
        agent_id: str = Header(alias="X-Agent-ID"),
    ) -> AppealRecord:
        return service.create_appeal(
            request_id,
            payload,
            token=_bearer(authorization),
            agent_id=agent_id,
            correlation_id=request.state.correlation_id,
        )

    @app.post("/v1/appeals/{appeal_id}/resolve", response_model=AppealRecord)
    def resolve_appeal_endpoint(
        appeal_id: str,
        payload: AppealResolutionRequest,
        request: Request,
        actor: str = Depends(require_admin),
    ) -> AppealRecord:
        return service.resolve_appeal(
            appeal_id,
            payload,
            actor_id=actor,
            correlation_id=request.state.correlation_id,
        )

    @app.get("/v1/rounds/{round_id}/appeals", response_model=list[AppealRecord])
    def list_round_appeals_endpoint(
        round_id: str, _actor: str = Depends(require_admin)
    ) -> list[AppealRecord]:
        return list(service.repository.list_round_appeals(round_id))

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "commonsgate.api:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        server_header=False,
    )
