"""PII-minimized tracing and structured request telemetry."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from opentelemetry import trace


LOGGER = logging.getLogger("commonsgate.telemetry")
TRACER = trace.get_tracer("commonsgate")
_CONFIGURED = False
_LOCK = threading.Lock()


def configure_cloud_trace(*, service_name: str, enabled: bool) -> bool:
    """Install the Google Cloud Trace exporter once when deployment enables it."""

    global _CONFIGURED
    if not enabled:
        return False
    with _LOCK:
        if _CONFIGURED:
            return True
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
        trace.set_tracer_provider(provider)
        _CONFIGURED = True
        return True


def current_span_attributes(**attributes: str | int | bool | None) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(f"commonsgate.{key}", value)


def log_event(event: str, **fields: Any) -> None:
    """Emit one JSON object without accepting arbitrary case payloads."""

    allowed = {
        "correlation_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "round_status",
        "transition_count",
        "paused_for_review",
    }
    safe = {key: value for key, value in fields.items() if key in allowed}
    LOGGER.info(json.dumps({"event": event, **safe}, sort_keys=True))

