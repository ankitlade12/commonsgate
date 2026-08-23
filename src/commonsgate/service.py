"""Application service orchestrating intake, freeze, and deterministic allocation."""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timedelta, timezone

from .allocator import allocate
from .audit import AuditLog
from .auth import DelegationTokenService, ReplayProtector
from .canonical import candidate_manifest_hash, seed_commitment, sha256_hex
from .contracts import (
    AppealCreateRequest,
    AppealRecord,
    AppealResolutionRequest,
    AppealStatus,
    DemoProofBundle,
    FieldProvenance,
    IntakeSubmission,
    LocalizedExplanation,
    MetricInterval,
    NormalizationResult,
    OfferDecisionRequest,
    RequestReceipt,
    RequestStatus,
    ReviewCorrection,
    RoundCreateRequest,
    RoundPublicProof,
    RoundRecord,
    RoundStatus,
    ShadowAuditReport,
    ShadowAuditRequest,
    StewardTickReport,
    StewardTickRequest,
    StoredRequest,
    ThreatCheck,
    ThreatReport,
)
from .errors import CommonsGateError, invalid_state
from .explanations import ExplanationTranslator
from .models import Charter, Request
from .normalization import Normalizer, validate_normalization
from .repository import Repository
from .simulator import generate_requests, run_demo, run_shadow_audit


class CommonsGateService:
    def __init__(
        self,
        *,
        repository: Repository,
        normalizer: Normalizer,
        token_service: DelegationTokenService,
        replay_protector: ReplayProtector,
        audit_log: AuditLog,
        explanation_translator: ExplanationTranslator,
    ) -> None:
        self.repository = repository
        self.normalizer = normalizer
        self.token_service = token_service
        self.replay_protector = replay_protector
        self.audit_log = audit_log
        self.explanation_translator = explanation_translator
        self._idempotency: dict[tuple[str, str], tuple[str, RequestReceipt]] = {}
        self._lock = threading.RLock()

    def create_round(
        self, request: RoundCreateRequest, *, actor_id: str, correlation_id: str
    ) -> RoundRecord:
        record = RoundRecord(**request.model_dump(), status=RoundStatus.DRAFT)
        self.repository.create_round(record)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="ROUND_CREATED",
            object_type="round",
            object_id=record.round_id,
            payload={
                "program_id": record.program_id,
                "policy_version": record.policy_version,
                "capacity": record.capacity,
                "seed_commitment": record.seed_commitment,
            },
        )
        return record

    def open_round(
        self, round_id: str, *, actor_id: str, correlation_id: str
    ) -> RoundRecord:
        record = self.repository.get_round(round_id)
        if record.status != RoundStatus.DRAFT:
            raise invalid_state("Only a draft round can be opened.")
        record = record.model_copy(update={"status": RoundStatus.OPEN})
        self.repository.save_round(record)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="ROUND_OPENED",
            object_type="round",
            object_id=round_id,
        )
        return record

    async def submit_request(
        self,
        submission: IntakeSubmission,
        *,
        token: str,
        agent_id: str,
        idempotency_key: str,
        nonce: str,
        correlation_id: str,
    ) -> RequestReceipt:
        if not 8 <= len(idempotency_key) <= 256:
            raise CommonsGateError(
                "IDEMPOTENCY_KEY_INVALID",
                "An idempotency key of 8–256 characters is required.",
            )
        claims = self.token_service.verify(
            token,
            agent_id=agent_id,
            provider_id=submission.provider_id,
            program_id=submission.program_id,
            principal_token=submission.principal_token,
            required_scope="submit",
        )
        # Server receipt time is intentionally excluded so a transport retry of
        # the same semantic request remains idempotent.
        payload_hash = sha256_hex(
            submission.model_dump(mode="json", exclude={"submitted_at"})
        )
        cache_key = (agent_id, idempotency_key)
        with self._lock:
            cached = self._idempotency.get(cache_key)
            if cached:
                cached_hash, cached_receipt = cached
                if cached_hash != payload_hash:
                    raise CommonsGateError(
                        "IDEMPOTENCY_CONFLICT",
                        "The idempotency key was already used with different content.",
                        status_code=409,
                    )
                return cached_receipt.model_copy(deep=True)

        self.replay_protector.consume(claims.delegation_id, nonce)
        round_record = self.repository.get_round(submission.round_id)
        self._assert_submission_matches_round(submission, round_record)
        if round_record.status != RoundStatus.OPEN:
            raise CommonsGateError(
                "ROUND_CLOSED", "The intake round is not open.", status_code=409
            )

        normalization = await self.normalizer.normalize(
            submission.raw_text,
            source_id=submission.evidence_reference or "submission_text",
        )
        normalization = validate_normalization(
            normalization, raw_text=submission.raw_text
        )
        status, reason_code, next_action, priority = self._classify(
            normalization=normalization,
            reference_date=round_record.policy_reference_date,
        )

        existing = self.repository.find_principal_request(
            submission.program_id, submission.round_id, submission.principal_token
        )
        if existing:
            receipt = self._merge_duplicate(
                existing,
                normalization=normalization,
                correlation_id=correlation_id,
                actor_id=agent_id,
                payload_hash=payload_hash,
            )
            with self._lock:
                self._idempotency[cache_key] = (payload_hash, receipt)
            return receipt

        request_id = f"req_{uuid.uuid4().hex}"
        stored = StoredRequest(
            request_id=request_id,
            provider_id=submission.provider_id,
            program_id=submission.program_id,
            round_id=submission.round_id,
            principal_token=submission.principal_token,
            agent_id=agent_id,
            delegation_id=claims.delegation_id,
            submitted_at=submission.submitted_at,
            raw_content_hash=payload_hash,
            evidence_reference=submission.evidence_reference,
            normalization=normalization,
            response_language=submission.response_language,
            status=status,
            reason_code=reason_code,
            priority_tier=priority,
            correlation_id=correlation_id,
        )
        self.repository.create_request(stored)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=agent_id,
            action="REQUEST_SUBMITTED",
            object_type="request",
            object_id=request_id,
            payload={
                "program_id": submission.program_id,
                "round_id": submission.round_id,
                "status": status.value,
                "reason_code": reason_code,
                "raw_content_hash": payload_hash,
                "model_identifier": normalization.model_identifier,
                "response_language": submission.response_language,
            },
        )
        receipt = self._receipt(stored, next_action=next_action)
        with self._lock:
            self._idempotency[cache_key] = (payload_hash, receipt)
        return receipt

    def get_request(
        self,
        request_id: str,
        *,
        token: str,
        agent_id: str,
        correlation_id: str,
    ) -> StoredRequest:
        stored = self.repository.get_request(request_id)
        self.token_service.verify(
            token,
            agent_id=agent_id,
            provider_id=stored.provider_id,
            program_id=stored.program_id,
            principal_token=stored.principal_token,
            required_scope="read_status",
        )
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=agent_id,
            action="REQUEST_STATUS_READ",
            object_type="request",
            object_id=request_id,
        )
        return stored

    async def explain_request(
        self,
        request_id: str,
        *,
        language_tag: str,
        token: str,
        agent_id: str,
        correlation_id: str,
    ) -> LocalizedExplanation:
        stored = self.get_request(
            request_id,
            token=token,
            agent_id=agent_id,
            correlation_id=correlation_id,
        )
        explanation = await self.explanation_translator.explain(
            stored.reason_code, language_tag
        )
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=agent_id,
            action="REQUEST_EXPLANATION_DELIVERED",
            object_type="request",
            object_id=request_id,
            payload={
                "reason_code": stored.reason_code,
                "requested_language": explanation.requested_language,
                "delivered_language": explanation.delivered_language,
                "fallback_used": explanation.fallback_used,
            },
        )
        return explanation

    def correct_review(
        self,
        request_id: str,
        correction: ReviewCorrection,
        *,
        actor_id: str,
        correlation_id: str,
    ) -> StoredRequest:
        stored = self.repository.get_request(request_id)
        round_record = self.repository.get_round(stored.round_id)
        if round_record.status != RoundStatus.OPEN:
            raise invalid_state("Review corrections are accepted only while the round is open.")
        if stored.status not in {
            RequestStatus.PENDING_HUMAN_REVIEW,
            RequestStatus.NEEDS_INFORMATION,
        }:
            raise invalid_state("This request does not have an open review task.")
        if stored.request_version != correction.expected_request_version:
            raise CommonsGateError(
                "REQUEST_VERSION_CONFLICT",
                "The request changed after the reviewer opened it. Reload before saving.",
                status_code=409,
            )

        provenance: dict[str, FieldProvenance] = {}
        for field_name, value in correction.corrected_facts.model_dump().items():
            if value is not None:
                provenance[field_name] = FieldProvenance(
                    source=f"review:{actor_id}",
                    source_quote="Verified by authorized human reviewer",
                    method="human_correction",
                    confidence=1.0,
                    human_verified=True,
                )
        normalized = NormalizationResult(
            model_identifier="authorized-human-review",
            facts=correction.corrected_facts,
            field_provenance=provenance,
            missing_information=[
                name
                for name, value in correction.corrected_facts.model_dump().items()
                if value is None and name != "preferred_language"
            ],
        )
        status, reason_code, _next_action, priority = self._classify(
            normalization=normalized,
            reference_date=round_record.policy_reference_date,
        )
        updated = stored.model_copy(
            update={
                "normalization": normalized,
                "normalization_history": (
                    *stored.normalization_history,
                    stored.normalization,
                ),
                "request_version": stored.request_version + 1,
                "status": status,
                "reason_code": reason_code,
                "priority_tier": priority,
                "response_language": stored.response_language,
            }
        )
        self.repository.save_request(updated)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="HUMAN_REVIEW_CORRECTED",
            object_type="request",
            object_id=request_id,
            payload={
                "prior_version": stored.request_version,
                "new_version": updated.request_version,
                "prior_status": stored.status.value,
                "new_status": updated.status.value,
                "reason_code": updated.reason_code,
                "reviewer_note_hash": sha256_hex(correction.reviewer_note),
            },
        )
        return updated

    def close_round(
        self, round_id: str, *, actor_id: str, correlation_id: str
    ) -> RoundRecord:
        record = self.repository.get_round(round_id)
        if record.status != RoundStatus.OPEN:
            raise invalid_state("Only an open round can be frozen.")
        qualified = self.repository.list_round_requests(
            round_id, status=RequestStatus.QUALIFIED_FOR_ROUND
        )
        allocator_requests = [self._to_allocator_request(item) for item in qualified]
        manifest_hash = candidate_manifest_hash(
            request.policy_facts() for request in allocator_requests
        )
        frozen_ids = tuple(item.request_id for item in qualified)
        for item in qualified:
            self.repository.save_request(
                item.model_copy(update={"status": RequestStatus.FROZEN})
            )
        record = record.model_copy(
            update={
                "status": RoundStatus.FROZEN,
                "frozen_request_ids": frozen_ids,
                "manifest_hash": manifest_hash,
            }
        )
        self.repository.save_round(record)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="ROUND_FROZEN",
            object_type="round",
            object_id=round_id,
            payload={
                "manifest_hash": manifest_hash,
                "qualified_count": len(frozen_ids),
            },
        )
        return record

    def allocate_round(
        self,
        round_id: str,
        *,
        seed: str,
        actor_id: str,
        correlation_id: str,
        now: datetime | None = None,
    ) -> RoundRecord:
        record = self.repository.get_round(round_id)
        if record.status != RoundStatus.FROZEN:
            raise invalid_state("Only a frozen round can be allocated.")
        if seed_commitment(seed) != record.seed_commitment:
            raise CommonsGateError(
                "SEED_COMMITMENT_MISMATCH",
                "The revealed seed does not match the precommitted seed.",
                status_code=409,
            )
        frozen = [
            self.repository.get_request(request_id)
            for request_id in record.frozen_request_ids
        ]
        allocatable_capacity = record.capacity - record.appeal_holdback_capacity
        charter = Charter(
            charter_id=f"{record.program_id}-charter",
            version=record.policy_version,
            capacity=allocatable_capacity,
            reserved_accommodation_capacity=record.reserved_accommodation_capacity,
        )
        result = allocate(
            [self._to_allocator_request(item) for item in frozen], charter, seed=seed
        )
        if result.manifest_hash != record.manifest_hash:
            raise CommonsGateError(
                "MANIFEST_MISMATCH",
                "The frozen request set changed before allocation.",
                status_code=409,
            )
        allocated = set(result.allocated_principals)
        published_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        waitlist_positions = {
            principal: index
            for index, principal in enumerate(result.waitlisted_principals, start=1)
        }
        for item in frozen:
            new_status = (
                RequestStatus.APPOINTMENT_OFFERED
                if item.principal_token in allocated
                else RequestStatus.WAITLISTED
            )
            offer_expires_at = (
                published_at + timedelta(minutes=record.offer_ttl_minutes)
                if new_status == RequestStatus.APPOINTMENT_OFFERED
                else None
            )
            self.repository.save_request(
                item.model_copy(
                    update={
                        "status": new_status,
                        "reason_code": new_status.value,
                        "offer_expires_at": offer_expires_at,
                        "offer_source": (
                            "initial"
                            if new_status == RequestStatus.APPOINTMENT_OFFERED
                            else None
                        ),
                        "waitlist_position": waitlist_positions.get(
                            item.principal_token
                        ),
                    }
                )
            )
        record = record.model_copy(
            update={
                "status": RoundStatus.PUBLISHED,
                "outcome_hash": result.outcome_hash,
                "revealed_seed": seed,
                "allocated_principals": result.allocated_principals,
                "waitlisted_principals": result.waitlisted_principals,
                "published_at": published_at,
            }
        )
        self.repository.save_round(record)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="ALLOCATION_PUBLISHED",
            object_type="round",
            object_id=round_id,
            payload={
                "manifest_hash": result.manifest_hash,
                "outcome_hash": result.outcome_hash,
                "seed_commitment": result.seed_commitment,
                "allocated_count": len(result.allocated_principals),
                "waitlisted_count": len(result.waitlisted_principals),
                "appeal_holdback_capacity": record.appeal_holdback_capacity,
            },
        )
        return record

    def steward_tick(
        self,
        round_id: str,
        payload: StewardTickRequest,
        *,
        actor_id: str,
        correlation_id: str,
    ) -> StewardTickReport:
        """Advance one round through safe, idempotent lifecycle transitions.

        A scheduler or ADK tool can call this repeatedly. The steward controls
        workflow timing; deterministic services retain all decision authority.
        """

        transitions: list[str] = []
        expired_count = 0
        promoted: tuple[str, ...] = ()
        paused = False
        pending_count = 0
        with self._lock:
            record = self.repository.get_round(round_id)
            if record.status == RoundStatus.DRAFT:
                if record.opens_at is None or payload.now >= record.opens_at:
                    record = self.open_round(
                        round_id,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                    )
                    transitions.append("ROUND_OPENED")
            elif record.status == RoundStatus.OPEN:
                due = record.closes_at is None or payload.now >= record.closes_at
                if due:
                    pending_count = sum(
                        item.status == RequestStatus.PENDING_HUMAN_REVIEW
                        for item in self.repository.list_round_requests(round_id)
                    )
                    if pending_count:
                        paused = True
                        self.audit_log.append(
                            correlation_id=correlation_id,
                            actor_id=actor_id,
                            action="STEWARD_PAUSED_FOR_REVIEW",
                            object_type="round",
                            object_id=round_id,
                            payload={"pending_review_count": pending_count},
                        )
                    else:
                        self.close_round(
                            round_id,
                            actor_id=actor_id,
                            correlation_id=correlation_id,
                        )
                        transitions.append("ROUND_FROZEN")
                        record = self.allocate_round(
                            round_id,
                            seed=payload.seed,
                            actor_id=actor_id,
                            correlation_id=correlation_id,
                            now=payload.now,
                        )
                        transitions.append("ALLOCATION_PUBLISHED")
            elif record.status == RoundStatus.PUBLISHED:
                expired_count, promoted = self.process_offer_expiry(
                    round_id,
                    now=payload.now,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                )
                if expired_count:
                    transitions.append("OFFERS_EXPIRED")
                if promoted:
                    transitions.append("WAITLIST_PROMOTED")

            record = self.repository.get_round(round_id)
        return StewardTickReport(
            round_id=round_id,
            status=record.status,
            transitions=tuple(transitions),
            paused_for_review=paused,
            pending_review_count=pending_count,
            expired_offer_count=expired_count,
            promoted_request_ids=promoted,
            idempotent_noop=not transitions and not paused,
        )

    def decide_offer(
        self,
        request_id: str,
        decision: OfferDecisionRequest,
        *,
        token: str,
        agent_id: str,
        correlation_id: str,
    ) -> StoredRequest:
        with self._lock:
            stored = self.repository.get_request(request_id)
            self.token_service.verify(
                token,
                agent_id=agent_id,
                provider_id=stored.provider_id,
                program_id=stored.program_id,
                principal_token=stored.principal_token,
                required_scope="manage_offer",
            )
            if stored.status != RequestStatus.APPOINTMENT_OFFERED:
                raise invalid_state("Only an active appointment offer can be decided.")
            if (
                stored.offer_expires_at is not None
                and stored.offer_expires_at <= datetime.now(timezone.utc)
            ):
                raise invalid_state(
                    "This offer has expired. Run the round steward to promote the waitlist."
                )
            new_status = (
                RequestStatus.OFFER_ACCEPTED
                if decision.decision == "accept"
                else RequestStatus.OFFER_DECLINED
            )
            updated = stored.model_copy(
                update={"status": new_status, "reason_code": new_status.value}
            )
            self.repository.save_request(updated)
            self.audit_log.append(
                correlation_id=correlation_id,
                actor_id=agent_id,
                action=new_status.value,
                object_type="request",
                object_id=request_id,
                payload={"round_id": stored.round_id, "offer_source": stored.offer_source},
            )
            if (
                new_status == RequestStatus.OFFER_DECLINED
                and stored.offer_source != "appeal_holdback"
            ):
                self._promote_waitlist(
                    stored.round_id,
                    now=datetime.now(timezone.utc),
                    actor_id="round-steward",
                    correlation_id=correlation_id,
                )
            return updated

    def process_offer_expiry(
        self,
        round_id: str,
        *,
        now: datetime,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[int, tuple[str, ...]]:
        expired = 0
        promotable_expired = 0
        with self._lock:
            for stored in self.repository.list_round_requests(round_id):
                if (
                    stored.status == RequestStatus.APPOINTMENT_OFFERED
                    and stored.offer_expires_at is not None
                    and stored.offer_expires_at <= now
                ):
                    self.repository.save_request(
                        stored.model_copy(
                            update={
                                "status": RequestStatus.OFFER_EXPIRED,
                                "reason_code": RequestStatus.OFFER_EXPIRED.value,
                            }
                        )
                    )
                    expired += 1
                    if stored.offer_source != "appeal_holdback":
                        promotable_expired += 1
                    self.audit_log.append(
                        correlation_id=correlation_id,
                        actor_id=actor_id,
                        action="OFFER_EXPIRED",
                        object_type="request",
                        object_id=stored.request_id,
                        payload={"round_id": round_id},
                    )
            promoted = tuple(
                request_id
                for _ in range(promotable_expired)
                if (
                    request_id := self._promote_waitlist(
                        round_id,
                        now=now,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                    )
                )
            )
            return expired, promoted

    def _promote_waitlist(
        self,
        round_id: str,
        *,
        now: datetime,
        actor_id: str,
        correlation_id: str,
    ) -> str | None:
        record = self.repository.get_round(round_id)
        for principal in record.waitlisted_principals:
            stored = self.repository.find_principal_request(
                record.program_id, round_id, principal
            )
            if stored is None or stored.status != RequestStatus.WAITLISTED:
                continue
            updated = stored.model_copy(
                update={
                    "status": RequestStatus.APPOINTMENT_OFFERED,
                    "reason_code": "WAITLIST_PROMOTED",
                    "offer_expires_at": now
                    + timedelta(minutes=record.offer_ttl_minutes),
                    "offer_source": "waitlist_promotion",
                }
            )
            self.repository.save_request(updated)
            self.repository.save_round(
                record.model_copy(update={"promotion_count": record.promotion_count + 1})
            )
            self.audit_log.append(
                correlation_id=correlation_id,
                actor_id=actor_id,
                action="WAITLIST_PROMOTED",
                object_type="request",
                object_id=stored.request_id,
                payload={
                    "round_id": round_id,
                    "waitlist_position": stored.waitlist_position,
                },
            )
            return stored.request_id
        return None

    def create_appeal(
        self,
        request_id: str,
        payload: AppealCreateRequest,
        *,
        token: str,
        agent_id: str,
        correlation_id: str,
    ) -> AppealRecord:
        stored = self.repository.get_request(request_id)
        self.token_service.verify(
            token,
            agent_id=agent_id,
            provider_id=stored.provider_id,
            program_id=stored.program_id,
            principal_token=stored.principal_token,
            required_scope="appeal",
        )
        round_record = self.repository.get_round(stored.round_id)
        if round_record.status != RoundStatus.PUBLISHED:
            raise invalid_state("An appeal can be filed only after results are published.")
        if stored.status not in {
            RequestStatus.WAITLISTED,
            RequestStatus.INELIGIBLE,
            RequestStatus.OFFER_EXPIRED,
        }:
            raise invalid_state("This request does not currently have an appealable result.")
        appeal = AppealRecord(
            appeal_id=f"appeal_{uuid.uuid4().hex}",
            request_id=request_id,
            round_id=stored.round_id,
            principal_token=stored.principal_token,
            requested_remedy=payload.requested_remedy,
            reason_hash=sha256_hex(payload.reason),
        )
        self.repository.create_appeal(appeal)
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=agent_id,
            action="APPEAL_FILED",
            object_type="appeal",
            object_id=appeal.appeal_id,
            payload={
                "round_id": stored.round_id,
                "request_id_hash": sha256_hex(request_id),
                "requested_remedy": payload.requested_remedy,
                "reason_hash": appeal.reason_hash,
            },
        )
        return appeal

    def resolve_appeal(
        self,
        appeal_id: str,
        payload: AppealResolutionRequest,
        *,
        actor_id: str,
        correlation_id: str,
    ) -> AppealRecord:
        with self._lock:
            appeal = self.repository.get_appeal(appeal_id)
            if appeal.status != AppealStatus.PENDING:
                raise invalid_state("Only a pending appeal can be resolved.")
            if appeal.version != payload.expected_version:
                raise CommonsGateError(
                    "APPEAL_VERSION_CONFLICT",
                    "The appeal changed after the reviewer opened it.",
                    status_code=409,
                )
            record = self.repository.get_round(appeal.round_id)
            remedy = payload.remedy
            if payload.outcome == "DENIED" and remedy != "NO_CHANGE":
                raise CommonsGateError(
                    "APPEAL_REMEDY_INVALID",
                    "A denied appeal must use the NO_CHANGE remedy.",
                )
            if payload.outcome == "GRANTED" and remedy == "NO_CHANGE":
                raise CommonsGateError(
                    "APPEAL_REMEDY_INVALID",
                    "A granted appeal must specify a concrete remedy.",
                )
            if remedy == "APPEAL_HOLDBACK_OFFER":
                granted_holdbacks = sum(
                    item.status == AppealStatus.GRANTED
                    and item.remedy == "APPEAL_HOLDBACK_OFFER"
                    for item in self.repository.list_round_appeals(appeal.round_id)
                )
                if granted_holdbacks >= record.appeal_holdback_capacity:
                    raise CommonsGateError(
                        "APPEAL_HOLDBACK_EXHAUSTED",
                        "No provider-approved appeal holdback remains.",
                        status_code=409,
                    )
                stored = self.repository.get_request(appeal.request_id)
                self.repository.save_request(
                    stored.model_copy(
                        update={
                            "status": RequestStatus.APPOINTMENT_OFFERED,
                            "reason_code": "APPEAL_REMEDY_OFFERED",
                            "offer_expires_at": datetime.now(timezone.utc)
                            + timedelta(minutes=record.offer_ttl_minutes),
                            "offer_source": "appeal_holdback",
                        }
                    )
                )

            resolved = appeal.model_copy(
                update={
                    "status": (
                        AppealStatus.GRANTED
                        if payload.outcome == "GRANTED"
                        else AppealStatus.DENIED
                    ),
                    "resolved_at": datetime.now(timezone.utc),
                    "remedy": remedy,
                    "reviewer_note_hash": sha256_hex(payload.reviewer_note),
                    "version": appeal.version + 1,
                }
            )
            self.repository.save_appeal(resolved)
            ledger_hash = sha256_hex(
                {
                    "domain": "commonsgate.remedy-ledger.v1",
                    "prior_hash": record.remedy_ledger_hash or "GENESIS",
                    "appeal_id": resolved.appeal_id,
                    "outcome": resolved.status.value,
                    "remedy": resolved.remedy,
                    "version": resolved.version,
                }
            )
            self.repository.save_round(
                record.model_copy(
                    update={
                        "remedy_count": record.remedy_count + 1,
                        "remedy_ledger_hash": ledger_hash,
                    }
                )
            )
            self.audit_log.append(
                correlation_id=correlation_id,
                actor_id=actor_id,
                action="APPEAL_RESOLVED",
                object_type="appeal",
                object_id=appeal_id,
                payload={
                    "round_id": appeal.round_id,
                    "outcome": resolved.status.value,
                    "remedy": remedy,
                    "reviewer_note_hash": resolved.reviewer_note_hash,
                    "remedy_ledger_hash": ledger_hash,
                },
            )
            return resolved

    @staticmethod
    def _interval(values: tuple[float, ...]) -> MetricInterval:
        ordered = sorted(values)
        p10_index = max(0, int((len(ordered) - 1) * 0.10))
        p90_index = min(len(ordered) - 1, int((len(ordered) - 1) * 0.90))
        return MetricInterval(
            mean=sum(ordered) / len(ordered),
            p10=ordered[p10_index],
            p90=ordered[p90_index],
        )

    def shadow_audit(self, payload: ShadowAuditRequest) -> ShadowAuditReport:
        data = run_shadow_audit(
            population_size=payload.population_size,
            capacity=payload.capacity,
            seed_runs=payload.seed_runs,
        )
        tier_size = payload.population_size // 4
        suppressed = tuple(
            tier
            for tier in sorted(data.baseline_rates)
            if tier_size < payload.small_cell_threshold
        )
        baseline_rates = {
            tier: None if tier in suppressed else rate
            for tier, rate in data.baseline_rates.items()
        }
        commonsgate_rates = {
            tier: (
                None
                if tier in suppressed
                else self._interval(data.commonsgate_rate_values[tier])
            )
            for tier in sorted(data.commonsgate_rate_values)
        }
        report_payload = {
            "population_size": data.population_size,
            "capacity": data.capacity,
            "seed_runs": data.seed_runs,
            "baseline_aai": data.baseline_aai,
            "commonsgate_aai": data.commonsgate_aai_values,
            "counterfactual": data.exact_counterfactual_change_rate,
            "small_cell_threshold": payload.small_cell_threshold,
        }
        return ShadowAuditReport(
            population_size=data.population_size,
            capacity=data.capacity,
            seed_runs=data.seed_runs,
            total_attempts=data.total_attempts,
            retry_attempts_neutralized=data.retry_attempts_neutralized,
            baseline_unique_people_served=data.baseline_unique_people_served,
            baseline_agent_advantage_index=data.baseline_aai,
            baseline_rates=baseline_rates,
            commonsgate_agent_advantage_index=self._interval(
                data.commonsgate_aai_values
            ),
            commonsgate_rates=commonsgate_rates,
            exact_agent_counterfactual_change_rate=(
                data.exact_counterfactual_change_rate
            ),
            small_cell_threshold=payload.small_cell_threshold,
            suppressed_tiers=suppressed,
            report_hash=sha256_hex(report_payload),
        )

    def threat_report(self) -> ThreatReport:
        report = run_demo()
        result = report.commonsgate
        attempts = generate_requests(population_size=report.population_size)
        replay = allocate(
            attempts,
            Charter(
                charter_id="housing-legal-intake",
                version="1.0.0",
                capacity=report.capacity,
                reserved_accommodation_capacity=min(4, report.capacity),
            ),
            seed="demo-seed-v1",
        )
        checks = (
            ThreatCheck(
                threat="retry_flood",
                control="Principal-level canonicalization",
                passed=result.duplicate_attempts_neutralized
                == len(attempts) - report.population_size,
                evidence=f"{result.duplicate_attempts_neutralized} retries neutralized",
            ),
            ThreatCheck(
                threat="premium_agent_switch",
                control="Agent metadata excluded from allocation",
                passed=all(
                    value == 0.0 for value in report.counterfactual_change_rates.values()
                ),
                evidence="0.0% counterfactual outcome change across all agent tiers",
            ),
            ThreatCheck(
                threat="capacity_overrun",
                control="Allocator capacity invariant",
                passed=len(result.allocated_principals) <= report.capacity,
                evidence=f"{len(result.allocated_principals)} of {report.capacity} slots allocated",
            ),
            ThreatCheck(
                threat="seed_substitution",
                control="Precommitted seed hash",
                passed=result.seed_commitment == seed_commitment("demo-seed-v1"),
                evidence="Revealed seed matches the published commitment",
            ),
            ThreatCheck(
                threat="outcome_tampering",
                control="Deterministic replay",
                passed=replay.outcome_hash == result.outcome_hash,
                evidence="Independent replay reproduced the outcome hash",
            ),
            ThreatCheck(
                threat="language_priority_leak",
                control="Canonical policy-fact allowlist",
                passed=all(
                    "language" not in key
                    for request in attempts
                    for key in request.policy_facts()
                ),
                evidence="Language is absent from every allocator input",
            ),
        )
        generated_at = datetime.now(timezone.utc)
        passed_count = sum(check.passed for check in checks)
        report_hash = sha256_hex(
            {
                "domain": "commonsgate.threat-report.v1",
                "checks": [check.model_dump(mode="json") for check in checks],
            }
        )
        return ThreatReport(
            generated_at=generated_at,
            checks=checks,
            passed_count=passed_count,
            total_count=len(checks),
            report_hash=report_hash,
        )

    def demo_proof(self) -> DemoProofBundle:
        report = run_demo()
        attempts = generate_requests(population_size=report.population_size)
        result = report.commonsgate
        replay = allocate(
            attempts,
            Charter(
                charter_id="housing-legal-intake",
                version="1.0.0",
                capacity=report.capacity,
                reserved_accommodation_capacity=min(4, report.capacity),
            ),
            seed="demo-seed-v1",
        )
        return DemoProofBundle(
            generated_at=datetime.now(timezone.utc),
            population_size=report.population_size,
            capacity=report.capacity,
            total_attempts=len(attempts),
            retry_attempts_neutralized=result.duplicate_attempts_neutralized,
            baseline_unique_people_served=len(set(report.baseline_unique_principals)),
            commonsgate_unique_people_served=len(result.allocated_principals),
            baseline_agent_advantage_index=report.baseline_aai,
            commonsgate_agent_advantage_index=report.commonsgate_aai,
            individual_manual_to_premium_sensitivity=(
                report.individual_agent_switch_sensitivity
            ),
            allocation_rates_by_agent_tier={
                "fifo": report.baseline_rates,
                "commonsgate": report.commonsgate_rates,
            },
            counterfactual_outcome_change_rate=report.counterfactual_change_rates,
            invariants={
                "capacity_respected": len(result.allocated_principals)
                <= report.capacity,
                "one_person_one_chance": len(set(result.allocated_principals))
                == len(result.allocated_principals),
                "retry_invariant": result.duplicate_attempts_neutralized
                == len(attempts) - report.population_size,
                "agent_tier_invariant": all(
                    change == 0.0
                    for change in report.counterfactual_change_rates.values()
                ),
                "language_excluded_from_allocation": all(
                    "language" not in key
                    for request in attempts
                    for key in request.policy_facts()
                ),
                "deterministic_replay": (
                    replay.manifest_hash == result.manifest_hash
                    and replay.seed_commitment == result.seed_commitment
                    and replay.outcome_hash == result.outcome_hash
                ),
            },
            cryptographic_proof={
                "manifest_hash": result.manifest_hash,
                "seed_commitment": result.seed_commitment,
                "outcome_hash": result.outcome_hash,
            },
        )

    def public_round_proof(self, round_id: str) -> RoundPublicProof:
        record = self.repository.get_round(round_id)
        if (
            record.status != RoundStatus.PUBLISHED
            or record.manifest_hash is None
            or record.outcome_hash is None
            or record.revealed_seed is None
        ):
            raise invalid_state("A public proof is available only after publication.")

        frozen = [
            self.repository.get_request(request_id)
            for request_id in record.frozen_request_ids
        ]
        replay = allocate(
            [self._to_allocator_request(item) for item in frozen],
            Charter(
                charter_id=f"{record.program_id}-charter",
                version=record.policy_version,
                capacity=record.capacity - record.appeal_holdback_capacity,
                reserved_accommodation_capacity=record.reserved_accommodation_capacity,
            ),
            seed=record.revealed_seed,
        )
        all_requests = self.repository.list_round_requests(round_id)
        return RoundPublicProof(
            round_id=record.round_id,
            program_id=record.program_id,
            policy_version=record.policy_version,
            capacity=record.capacity,
            candidate_count=len(record.frozen_request_ids),
            allocated_count=len(record.allocated_principals),
            waitlisted_count=len(record.waitlisted_principals),
            review_count=sum(
                item.status == RequestStatus.PENDING_HUMAN_REVIEW
                for item in all_requests
            ),
            appeal_holdback_capacity=record.appeal_holdback_capacity,
            promotion_count=record.promotion_count,
            remedy_count=record.remedy_count,
            remedy_ledger_hash=record.remedy_ledger_hash,
            manifest_hash=record.manifest_hash,
            seed_commitment=record.seed_commitment,
            revealed_seed=record.revealed_seed,
            outcome_hash=record.outcome_hash,
            audit_chain_valid=self.audit_log.verify_chain(),
            replay_verified=(
                replay.manifest_hash == record.manifest_hash
                and replay.outcome_hash == record.outcome_hash
                and replay.seed_commitment == record.seed_commitment
            ),
            privacy_statement=(
                "This proof contains aggregate counts and cryptographic commitments only; "
                "principal and agent identifiers are intentionally omitted."
            ),
        )

    @staticmethod
    def _assert_submission_matches_round(
        submission: IntakeSubmission, round_record: RoundRecord
    ) -> None:
        if (
            submission.provider_id != round_record.provider_id
            or submission.program_id != round_record.program_id
        ):
            raise CommonsGateError(
                "ROUND_SCOPE_MISMATCH",
                "The request does not match the round's provider and program.",
                status_code=409,
            )

    @staticmethod
    def _classify(
        *, normalization, reference_date: date
    ) -> tuple[RequestStatus, str, str, int | None]:
        if normalization.conflicts or normalization.safety_flags:
            return (
                RequestStatus.PENDING_HUMAN_REVIEW,
                "HUMAN_REVIEW_REQUIRED",
                "A staff member will verify the flagged information.",
                None,
            )
        if normalization.facts.service_area_confirmed is False:
            return (
                RequestStatus.INELIGIBLE,
                "OUTSIDE_SERVICE_AREA",
                "Review the service-area rule or request human support.",
                None,
            )
        if normalization.missing_information:
            return (
                RequestStatus.NEEDS_INFORMATION,
                "MORE_INFORMATION_REQUIRED",
                "Provide the specifically listed missing information.",
                None,
            )
        deadline = normalization.facts.court_deadline_date
        if deadline is None:
            priority = 3
        else:
            days = (deadline - reference_date).days
            if days < 0:
                return (
                    RequestStatus.PENDING_HUMAN_REVIEW,
                    "HUMAN_REVIEW_REQUIRED",
                    "A staff member must review the past deadline.",
                    None,
                )
            priority = 1 if days <= 3 else 2 if days <= 7 else 3
        return (
            RequestStatus.QUALIFIED_FOR_ROUND,
            "INCLUDED_IN_ROUND",
            "Wait for the intake window to close; applying again will not improve your chance.",
            priority,
        )

    def _merge_duplicate(
        self,
        existing: StoredRequest,
        *,
        normalization,
        correlation_id: str,
        actor_id: str,
        payload_hash: str,
    ) -> RequestReceipt:
        facts_changed = existing.normalization.facts != normalization.facts
        if facts_changed:
            updated = existing.model_copy(
                update={
                    "status": RequestStatus.PENDING_HUMAN_REVIEW,
                    "reason_code": "HUMAN_REVIEW_REQUIRED",
                    "normalization_history": (
                        *existing.normalization_history,
                        normalization,
                    ),
                    "request_version": existing.request_version + 1,
                }
            )
            self.repository.save_request(updated)
            reason = "DUPLICATE_FACT_CONFLICT"
            next_action = "A staff member will review conflicting submissions."
        else:
            updated = existing
            reason = "DUPLICATE_MERGED"
            next_action = "No action is required; this did not create another chance."
        self.audit_log.append(
            correlation_id=correlation_id,
            actor_id=actor_id,
            action="REQUEST_DEDUPLICATED",
            object_type="request",
            object_id=existing.request_id,
            payload={
                "reason_code": reason,
                "additional_content_hash": payload_hash,
                "facts_changed": facts_changed,
            },
        )
        return RequestReceipt(
            request_id=updated.request_id,
            round_id=updated.round_id,
            status=updated.status,
            reason_code=reason,
            next_action=next_action,
            policy_version=self.repository.get_round(updated.round_id).policy_version,
            normalization=updated.normalization,
            correlation_id=correlation_id,
            duplicate_of=updated.request_id,
            response_language=updated.response_language,
        )

    def _receipt(self, stored: StoredRequest, *, next_action: str) -> RequestReceipt:
        return RequestReceipt(
            request_id=stored.request_id,
            round_id=stored.round_id,
            status=stored.status,
            reason_code=stored.reason_code,
            next_action=next_action,
            policy_version=self.repository.get_round(stored.round_id).policy_version,
            normalization=stored.normalization,
            correlation_id=stored.correlation_id,
            response_language=stored.response_language,
        )

    @staticmethod
    def _to_allocator_request(stored: StoredRequest) -> Request:
        if stored.priority_tier is None:
            raise CommonsGateError(
                "REQUEST_NOT_QUALIFIED",
                "A request without a deterministic priority tier cannot be allocated.",
                status_code=409,
            )
        return Request(
            request_id=stored.request_id,
            principal_token=stored.principal_token,
            agent_id=stored.agent_id,
            agent_tier="free",  # Deliberately irrelevant at the allocation boundary.
            submitted_at_ms=int(stored.submitted_at.timestamp() * 1_000),
            priority_tier=stored.priority_tier,
            eligible=True,
            accommodation_requested=(
                stored.normalization.facts.accommodation_requested is True
            ),
        )
