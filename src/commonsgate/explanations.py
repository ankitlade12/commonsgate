"""Reason-code locked, language-neutral resident explanations."""

from __future__ import annotations

import asyncio
import os
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .contracts import LocalizedExplanation
from .errors import CommonsGateError


class ExplanationTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    message: str
    next_action: str


REASON_CATALOG: dict[str, ExplanationTemplate] = {
    "RECEIVED": ExplanationTemplate(
        title="Request received",
        message="Your authorized request was received.",
        next_action="Keep your receipt. We will update this status when processing begins.",
    ),
    "INCLUDED_IN_ROUND": ExplanationTemplate(
        title="Included in the allocation round",
        message=(
            "Your request meets the published intake rules and has one entry in this round. "
            "The kind or speed of agent you used does not change your chance."
        ),
        next_action="Wait for the intake window to close. Applying again will not improve your chance.",
    ),
    "MORE_INFORMATION_REQUIRED": ExplanationTemplate(
        title="More information is needed",
        message="One or more required facts could not be verified from the submitted information.",
        next_action="Provide the missing items shown on your request or ask a staff member for help.",
    ),
    "HUMAN_REVIEW_REQUIRED": ExplanationTemplate(
        title="A staff review is protecting your request",
        message=(
            "The system found information that should not be decided automatically. "
            "No allocation decision has been made for this request."
        ),
        next_action="A staff member will verify the flagged information and preserve the original record.",
    ),
    "OUTSIDE_SERVICE_AREA": ExplanationTemplate(
        title="Service-area rule not met",
        message="The submitted information does not establish eligibility under the published service-area rule.",
        next_action="Review the service-area rule or request human support if the information is incorrect.",
    ),
    "DUPLICATE_MERGED": ExplanationTemplate(
        title="Repeat request safely merged",
        message="This request was linked to the same represented person and did not create an extra chance.",
        next_action="No action is required unless the facts shown on your receipt are wrong.",
    ),
    "DUPLICATE_FACT_CONFLICT": ExplanationTemplate(
        title="Conflicting request information needs review",
        message="Two requests for the same represented person contained different policy-relevant facts.",
        next_action="A staff member will review both records without creating another allocation chance.",
    ),
    "APPOINTMENT_OFFERED": ExplanationTemplate(
        title="Appointment offered",
        message="Your request was selected under the published policy and committed tie-break procedure.",
        next_action="Follow the provider's acceptance instructions before the stated deadline.",
    ),
    "WAITLISTED": ExplanationTemplate(
        title="Placed on the waitlist",
        message="Your request was eligible, but this round had fewer appointments than eligible people.",
        next_action="Keep your receipt. The provider will contact you if a place becomes available.",
    ),
    "WAITLIST_PROMOTED": ExplanationTemplate(
        title="A place became available",
        message="Your request was next in the committed waitlist order and now has an appointment offer.",
        next_action="Accept the offer before its stated deadline or it will pass to the next person.",
    ),
    "OFFER_ACCEPTED": ExplanationTemplate(
        title="Offer accepted",
        message="Your acceptance was recorded for the offered appointment.",
        next_action="Follow the provider's appointment instructions.",
    ),
    "OFFER_DECLINED": ExplanationTemplate(
        title="Offer declined",
        message="Your decline was recorded and the place can now pass to the next eligible person.",
        next_action="No further action is required for this offer.",
    ),
    "OFFER_EXPIRED": ExplanationTemplate(
        title="Offer expired",
        message="The appointment offer was not accepted before the published deadline.",
        next_action="Contact human support if an accessibility or delivery problem prevented a response.",
    ),
    "APPEAL_REMEDY_OFFERED": ExplanationTemplate(
        title="Appeal remedy offered",
        message="An authorized review found that a provider-approved remedy should be offered from the appeal holdback.",
        next_action="Accept the remedy offer before its stated deadline.",
    ),
}


class ExplanationTranslator(Protocol):
    name: str

    async def explain(self, reason_code: str, language_tag: str) -> LocalizedExplanation: ...


def _template(reason_code: str) -> ExplanationTemplate:
    try:
        return REASON_CATALOG[reason_code]
    except KeyError as exc:
        raise CommonsGateError(
            "REASON_CODE_UNKNOWN",
            "No approved resident explanation exists for that reason code.",
            status_code=404,
        ) from exc


class TemplateExplanationTranslator:
    """Safe offline fallback. It declares English fallback instead of faking a translation."""

    name = "approved-template-catalog"

    async def explain(self, reason_code: str, language_tag: str) -> LocalizedExplanation:
        template = _template(reason_code)
        requested = language_tag
        delivered = "en"
        return LocalizedExplanation(
            reason_code=reason_code,
            requested_language=requested,
            delivered_language=delivered,
            title=template.title,
            message=template.message,
            next_action=template.next_action,
            fallback_used=requested.lower() != "en",
            model_identifier=self.name,
        )


class _TranslatedFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2_000)
    next_action: str = Field(min_length=1, max_length=1_000)


class GeminiExplanationTranslator:
    """Translates approved copy only; the reason code and decision remain application-owned."""

    name = "gemini-reason-translation"

    def __init__(self, *, model: str | None = None, client=None) -> None:
        from google import genai

        self.model = model or os.getenv("COMMONSGATE_GEMINI_MODEL") or "gemini-3.5-flash"
        self._client = client or genai.Client()
        self._fallback = TemplateExplanationTranslator()

    async def explain(self, reason_code: str, language_tag: str) -> LocalizedExplanation:
        template = _template(reason_code)
        if language_tag.lower() == "en":
            return await self._fallback.explain(reason_code, language_tag)

        prompt = (
            f"Target BCP 47 language tag: {language_tag}\n"
            f"Title: {template.title}\n"
            f"Message: {template.message}\n"
            f"Next action: {template.next_action}\n"
        )
        try:
            response = await asyncio.to_thread(
                lambda: self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "system_instruction": (
                            "Translate the three approved resident-facing fields faithfully into the target language. "
                            "Do not add, remove, soften, or reinterpret policy. Preserve dates, names, and negation. "
                            "Return only the requested JSON structure. You have no decision authority."
                        ),
                        "response_mime_type": "application/json",
                        "response_json_schema": _TranslatedFields.model_json_schema(),
                    },
                )
            )
            output_text = getattr(response, "text", None)
            if not isinstance(output_text, str):
                raise TypeError("Gemini response did not contain text")
            translated = _TranslatedFields.model_validate_json(output_text)
        except Exception:  # noqa: BLE001 - model failure must use safe approved copy
            # Translation failure must never hide the authoritative reason or status.
            return await self._fallback.explain(reason_code, language_tag)

        return LocalizedExplanation(
            reason_code=reason_code,
            requested_language=language_tag,
            delivered_language=language_tag,
            title=translated.title,
            message=translated.message,
            next_action=translated.next_action,
            fallback_used=False,
            model_identifier=self.model,
        )


def build_explanation_translator(mode: str | None = None) -> ExplanationTranslator:
    selected = (mode or os.getenv("COMMONSGATE_TRANSLATOR") or "template").lower()
    if selected == "gemini":
        return GeminiExplanationTranslator()
    if selected == "template":
        return TemplateExplanationTranslator()
    raise ValueError("COMMONSGATE_TRANSLATOR must be 'gemini' or 'template'")
