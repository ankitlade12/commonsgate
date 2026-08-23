"""Stable domain errors shared by the service and HTTP boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CommonsGateError(Exception):
    code: str
    message: str
    status_code: int = 400
    retryable: bool = False
    details: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


def invalid_state(message: str) -> CommonsGateError:
    return CommonsGateError("INVALID_STATE_TRANSITION", message, status_code=409)
