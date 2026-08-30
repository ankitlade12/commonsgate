"""Validated contracts at the model, service, and HTTP boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=160)]
PrincipalToken = Annotated[str, StringConstraints(min_length=16, max_length=256)]
LanguageTag = Annotated[
    str,
    StringConstraints(
        min_length=2,
        max_length=35,
        pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
    ),
]


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequestStatus(StrEnum):
    RECEIVED = "RECEIVED"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    QUALIFIED_FOR_ROUND = "QUALIFIED_FOR_ROUND"
    FROZEN = "FROZEN"
    APPOINTMENT_OFFERED = "APPOINTMENT_OFFERED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    OFFER_DECLINED = "OFFER_DECLINED"
    OFFER_EXPIRED = "OFFER_EXPIRED"
    WAITLISTED = "WAITLISTED"
    INELIGIBLE = "INELIGIBLE"


class RoundStatus(StrEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    FROZEN = "FROZEN"
    PUBLISHED = "PUBLISHED"


class DelegationClaims(StrictModel):
    delegation_id: Identifier
    principal_token: PrincipalToken
    agent_id: Identifier
    provider_id: Identifier
    program_id: Identifier
    scopes: frozenset[
        Literal[
            "submit",
            "read_status",
            "correct",
            "withdraw",
            "appeal",
            "manage_offer",
        ]
    ]
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return value.astimezone(UTC)


class DelegationIssueRequest(StrictModel):
    principal_token: PrincipalToken
    agent_id: Identifier
    provider_id: Identifier
    program_id: Identifier
    scopes: frozenset[
        Literal[
            "submit",
            "read_status",
            "correct",
            "withdraw",
            "appeal",
            "manage_offer",
        ]
    ]
    expires_in_minutes: int = Field(default=60, ge=1, le=1_440)


class DelegationIssueResponse(StrictModel):
    delegation_id: Identifier
    token: str
    expires_at: datetime


class FieldProvenance(StrictModel):
    source: Identifier
    source_quote: str = Field(min_length=1, max_length=500)
    method: Literal[
        "structured_submission",
        "gemini_extraction",
        "human_correction",
        "rule_fallback",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    human_verified: bool = False


class ExtractedFacts(StrictModel):
    service_area_confirmed: bool | None = Field(
        description="Whether the text explicitly establishes the configured service area."
    )
    court_deadline_date: date | None = Field(
        description="Explicit court or response deadline, never an inferred date."
    )
    accommodation_requested: bool | None = Field(
        description="Whether the applicant explicitly requests an accessibility accommodation."
    )
    preferred_language: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "Communication preference only. It is excluded from allocation facts."
        ),
    )


class NormalizationResult(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    model_identifier: Identifier
    prompt_template_version: Literal["intake-v1"] = "intake-v1"
    facts: ExtractedFacts
    field_provenance: dict[str, FieldProvenance]
    missing_information: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    decision_authority: Literal["none"] = "none"


class EnvelopeDelegate(StrictModel):
    agent_id: Identifier
    delegation_id: Identifier
    scopes: frozenset[
        Literal[
            "submit",
            "read_status",
            "correct",
            "withdraw",
            "appeal",
            "manage_offer",
        ]
    ]


class EnvelopePolicyFacts(StrictModel):
    """The complete fact allowlist visible to the allocation boundary."""

    service_area_confirmed: bool
    priority_tier: int = Field(ge=1)
    accommodation_requested: bool


class EnvelopeCommunicationPreferences(StrictModel):
    response_language: LanguageTag = "en"


class EnvelopeEvidence(StrictModel):
    evidence_id: Identifier
    type: Identifier
    content_hash: Annotated[
        str, StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$")
    ]
    storage_reference: str | None = Field(default=None, max_length=500)


class FairAccessEnvelope(StrictModel):
    """Portable, agent-neutral representation produced after validation/review."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    envelope_id: Identifier
    provider_id: Identifier
    program_id: Identifier
    round_id: Identifier
    principal_token: PrincipalToken
    delegate: EnvelopeDelegate
    policy_facts: EnvelopePolicyFacts
    field_provenance: dict[str, FieldProvenance]
    communication_preferences: EnvelopeCommunicationPreferences = Field(
        default_factory=EnvelopeCommunicationPreferences
    )
    evidence: tuple[EnvelopeEvidence, ...] = ()


class IntakeSubmission(StrictModel):
    provider_id: Identifier
    program_id: Identifier
    round_id: Identifier
    principal_token: PrincipalToken
    raw_text: str = Field(min_length=1, max_length=20_000)
    response_language: LanguageTag = Field(
        default="en",
        description=(
            "BCP 47 language tag for receipts and explanations. Never used by allocation."
        ),
    )
    evidence_reference: str | None = Field(default=None, max_length=500)
    submitted_at: datetime = Field(default_factory=utc_now)

    @field_validator("submitted_at")
    @classmethod
    def submitted_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("submitted_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("response_language")
    @classmethod
    def canonicalize_language_tag(cls, value: str) -> str:
        parts = value.split("-")
        canonical = [parts[0].lower()]
        for part in parts[1:]:
            if len(part) == 2 and part.isalpha():
                canonical.append(part.upper())
            elif len(part) == 4 and part.isalpha():
                canonical.append(part.title())
            else:
                canonical.append(part.lower())
        return "-".join(canonical)


class RequestReceipt(StrictModel):
    request_id: Identifier
    round_id: Identifier
    status: RequestStatus
    reason_code: Identifier
    next_action: str
    policy_version: Identifier
    normalization: NormalizationResult
    correlation_id: Identifier
    duplicate_of: Identifier | None = None
    response_language: LanguageTag = "en"


class StoredRequest(StrictModel):
    request_id: Identifier
    provider_id: Identifier
    program_id: Identifier
    round_id: Identifier
    principal_token: PrincipalToken
    agent_id: Identifier
    delegation_id: Identifier
    submitted_at: datetime
    raw_content_hash: Identifier
    evidence_reference: str | None
    normalization: NormalizationResult
    normalization_history: tuple[NormalizationResult, ...] = ()
    request_version: int = Field(default=1, ge=1)
    response_language: LanguageTag = "en"
    status: RequestStatus
    reason_code: Identifier
    priority_tier: int | None = Field(default=None, ge=1)
    correlation_id: Identifier
    offer_expires_at: datetime | None = None
    offer_source: Literal["initial", "waitlist_promotion", "appeal_holdback"] | None = None
    waitlist_position: int | None = Field(default=None, ge=1)


class RoundCreateRequest(StrictModel):
    round_id: Identifier
    provider_id: Identifier
    program_id: Identifier
    policy_version: Identifier
    policy_reference_date: date = Field(
        description="Fixed date used for every deadline calculation in the round."
    )
    capacity: int = Field(ge=0, le=100_000)
    reserved_accommodation_capacity: int = Field(default=0, ge=0, le=100_000)
    appeal_holdback_capacity: int = Field(default=0, ge=0, le=100_000)
    offer_ttl_minutes: int = Field(default=1_440, ge=1, le=43_200)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    seed_commitment: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]

    @field_validator("reserved_accommodation_capacity")
    @classmethod
    def reservation_fits_capacity(cls, value: int, info):
        capacity = info.data.get("capacity")
        if capacity is not None and value > capacity:
            raise ValueError("reserved capacity cannot exceed total capacity")
        return value

    @field_validator("appeal_holdback_capacity")
    @classmethod
    def holdback_fits_capacity(cls, value: int, info):
        capacity = info.data.get("capacity")
        if capacity is not None and value > capacity:
            raise ValueError("appeal holdback cannot exceed total capacity")
        reserved = info.data.get("reserved_accommodation_capacity", 0)
        if capacity is not None and reserved > capacity - value:
            raise ValueError(
                "accommodation reservation plus appeal holdback cannot exceed capacity"
            )
        return value

    @field_validator("opens_at", "closes_at")
    @classmethod
    def round_times_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("round automation times must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def automation_window_is_ordered(self) -> Self:
        if (
            self.opens_at is not None
            and self.closes_at is not None
            and self.closes_at <= self.opens_at
        ):
            raise ValueError("closes_at must be later than opens_at")
        return self


class RoundRecord(RoundCreateRequest):
    status: RoundStatus = RoundStatus.DRAFT
    frozen_request_ids: tuple[str, ...] = ()
    manifest_hash: str | None = None
    outcome_hash: str | None = None
    revealed_seed: str | None = Field(default=None, min_length=16, max_length=500)
    allocated_principals: tuple[str, ...] = ()
    waitlisted_principals: tuple[str, ...] = ()
    published_at: datetime | None = None
    promotion_count: int = Field(default=0, ge=0)
    remedy_count: int = Field(default=0, ge=0)
    remedy_ledger_hash: str | None = None


class SeedRevealRequest(StrictModel):
    seed: str = Field(min_length=16, max_length=500)


class StewardTickRequest(SeedRevealRequest):
    now: datetime = Field(default_factory=utc_now)

    @field_validator("now")
    @classmethod
    def now_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("now must include a timezone")
        return value.astimezone(UTC)


class StewardTickReport(StrictModel):
    round_id: Identifier
    status: RoundStatus
    transitions: tuple[str, ...]
    paused_for_review: bool
    pending_review_count: int = Field(ge=0)
    expired_offer_count: int = Field(ge=0)
    promoted_request_ids: tuple[Identifier, ...]
    idempotent_noop: bool


class OfferDecisionRequest(StrictModel):
    decision: Literal["accept", "decline"]


class AppealStatus(StrEnum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"


class AppealCreateRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=2_000)
    requested_remedy: Literal[
        "APPEAL_HOLDBACK_OFFER", "NEXT_ROUND_PRIORITY", "REVIEW_ONLY"
    ] = "REVIEW_ONLY"


class AppealResolutionRequest(StrictModel):
    outcome: Literal["GRANTED", "DENIED"]
    remedy: Literal[
        "APPEAL_HOLDBACK_OFFER", "NEXT_ROUND_PRIORITY", "NO_CHANGE"
    ]
    reviewer_note: str = Field(min_length=1, max_length=2_000)
    expected_version: int = Field(ge=1)


class AppealRecord(StrictModel):
    appeal_id: Identifier
    request_id: Identifier
    round_id: Identifier
    principal_token: PrincipalToken
    status: AppealStatus = AppealStatus.PENDING
    requested_remedy: Literal[
        "APPEAL_HOLDBACK_OFFER", "NEXT_ROUND_PRIORITY", "REVIEW_ONLY"
    ]
    reason_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None
    remedy: Literal[
        "APPEAL_HOLDBACK_OFFER", "NEXT_ROUND_PRIORITY", "NO_CHANGE"
    ] | None = None
    reviewer_note_hash: Annotated[
        str | None, StringConstraints(pattern=r"^[a-f0-9]{64}$")
    ] = None
    version: int = Field(default=1, ge=1)


class ShadowAuditRequest(StrictModel):
    population_size: int = Field(default=200, ge=20, le=800)
    capacity: int = Field(default=20, ge=1, le=400)
    seed_runs: int = Field(default=25, ge=5, le=40)
    small_cell_threshold: int = Field(default=10, ge=1, le=100)

    @field_validator("population_size")
    @classmethod
    def population_must_balance_demo_tiers(cls, value: int) -> int:
        if value % 4:
            raise ValueError("population_size must be a multiple of four")
        return value

    @field_validator("capacity")
    @classmethod
    def capacity_fits_population(cls, value: int, info):
        population = info.data.get("population_size")
        if population is not None and value > population:
            raise ValueError("capacity cannot exceed population_size")
        return value


class MetricInterval(StrictModel):
    mean: float = Field(ge=0.0, le=1.0)
    p10: float = Field(ge=0.0, le=1.0)
    p90: float = Field(ge=0.0, le=1.0)


class ShadowAuditReport(StrictModel):
    report_version: Literal["commonsgate-shadow-v1"] = "commonsgate-shadow-v1"
    synthetic_demo: Literal[True] = True
    population_size: int
    capacity: int
    seed_runs: int
    total_attempts: int
    retry_attempts_neutralized: int
    baseline_unique_people_served: int
    baseline_agent_advantage_index: float
    baseline_rates: dict[str, float | None]
    commonsgate_agent_advantage_index: MetricInterval
    commonsgate_rates: dict[str, MetricInterval | None]
    exact_agent_counterfactual_change_rate: float
    small_cell_threshold: int
    suppressed_tiers: tuple[str, ...]
    report_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ThreatCheck(StrictModel):
    threat: Identifier
    control: str
    passed: bool
    evidence: str


class ThreatReport(StrictModel):
    report_version: Literal["commonsgate-threats-v1"] = "commonsgate-threats-v1"
    generated_at: datetime
    checks: tuple[ThreatCheck, ...]
    passed_count: int
    total_count: int
    report_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ReviewCorrection(StrictModel):
    corrected_facts: ExtractedFacts
    reviewer_note: str = Field(min_length=1, max_length=2_000)
    expected_request_version: int = Field(ge=1)


class LocalizedExplanation(StrictModel):
    reason_code: Identifier
    requested_language: LanguageTag
    delivered_language: LanguageTag
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2_000)
    next_action: str = Field(min_length=1, max_length=1_000)
    fallback_used: bool
    template_version: Literal["reason-catalog-v1"] = "reason-catalog-v1"
    model_identifier: Identifier
    decision_authority: Literal["none"] = "none"


class DemoProofBundle(StrictModel):
    proof_version: Literal["commonsgate-proof-v1"] = "commonsgate-proof-v1"
    scenario_id: Literal["agent-access-200x20-v1"] = "agent-access-200x20-v1"
    generated_at: datetime
    synthetic_demo: Literal[True] = True
    population_size: int = Field(ge=1)
    capacity: int = Field(ge=0)
    total_attempts: int = Field(ge=0)
    retry_attempts_neutralized: int = Field(ge=0)
    baseline_unique_people_served: int = Field(ge=0)
    commonsgate_unique_people_served: int = Field(ge=0)
    baseline_agent_advantage_index: float = Field(ge=0.0, le=1.0)
    commonsgate_agent_advantage_index: float = Field(ge=0.0, le=1.0)
    individual_manual_to_premium_sensitivity: dict[str, float]
    allocation_rates_by_agent_tier: dict[str, dict[str, float]]
    counterfactual_outcome_change_rate: dict[str, float]
    invariants: dict[str, bool]
    cryptographic_proof: dict[str, str]


class AgentSwapCertificate(StrictModel):
    certificate_version: Literal["commonsgate-agent-swap-v1"] = (
        "commonsgate-agent-swap-v1"
    )
    scenario_id: Literal["agent-access-200x20-v1"] = "agent-access-200x20-v1"
    generated_at: datetime
    synthetic_demo: Literal[True] = True
    population_size: int = Field(ge=1)
    capacity: int = Field(ge=0)
    representations: tuple[Literal["manual", "free", "standard", "premium"], ...]
    representation_manifest_hashes: dict[
        Literal["manual", "free", "standard", "premium"],
        Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")],
    ]
    representation_outcome_hashes: dict[
        Literal["manual", "free", "standard", "premium"],
        Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")],
    ]
    seed_commitment: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    all_manifests_identical: bool
    all_outcomes_identical: bool
    maximum_outcome_change_rate: float = Field(ge=0.0, le=1.0)
    certificate_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    methodology: str = Field(min_length=1, max_length=1_000)


class RoundPublicProof(StrictModel):
    proof_version: Literal["commonsgate-proof-v1"] = "commonsgate-proof-v1"
    round_id: Identifier
    program_id: Identifier
    policy_version: Identifier
    status: Literal["PUBLISHED"] = "PUBLISHED"
    capacity: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    allocated_count: int = Field(ge=0)
    waitlisted_count: int = Field(ge=0)
    review_count: int = Field(ge=0)
    appeal_holdback_capacity: int = Field(ge=0)
    promotion_count: int = Field(ge=0)
    remedy_count: int = Field(ge=0)
    remedy_ledger_hash: str | None = None
    manifest_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    seed_commitment: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    revealed_seed: str = Field(min_length=16, max_length=500)
    outcome_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    audit_chain_valid: bool
    replay_verified: bool
    privacy_statement: str


class ErrorDetail(StrictModel):
    field: str | None = None
    reason: str


class ErrorBody(StrictModel):
    code: str
    message: str
    correlation_id: str
    retryable: bool
    human_support_available: bool = True
    details: list[dict] = Field(default_factory=list)


class ErrorResponse(StrictModel):
    error: ErrorBody
