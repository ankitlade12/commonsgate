"""PII-minimized, append-only, hash-chained audit events."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .canonical import sha256_hex


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    sequence: int = Field(ge=1)
    timestamp: datetime
    correlation_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    payload: dict[str, Any]
    prior_hash: str
    event_hash: str


class AuditLog:
    PROHIBITED_KEYS: ClassVar[set[str]] = {
        "raw_text",
        "name",
        "address",
        "email",
        "phone",
        "delegation_token",
        "token",
    }

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.RLock()

    def append(
        self,
        *,
        correlation_id: str,
        actor_id: str,
        action: str,
        object_type: str,
        object_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        safe_payload = payload or {}
        prohibited = self.PROHIBITED_KEYS.intersection(safe_payload)
        if prohibited:
            raise ValueError(f"prohibited audit payload keys: {sorted(prohibited)}")
        with self._lock:
            prior_hash = self._events[-1].event_hash if self._events else "GENESIS"
            timestamp = datetime.now(UTC)
            sequence = len(self._events) + 1
            event_base = {
                "sequence": sequence,
                "timestamp": timestamp.isoformat(),
                "correlation_id": correlation_id,
                "actor_id": actor_id,
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "payload": safe_payload,
                "prior_hash": prior_hash,
            }
            event = AuditEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_hash=sha256_hex(event_base),
                sequence=sequence,
                timestamp=timestamp,
                correlation_id=correlation_id,
                actor_id=actor_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                payload=safe_payload,
                prior_hash=prior_hash,
            )
            self._events.append(event)
            return event

    def list_for_object(self, object_id: str) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(
                event for event in self._events if event.object_id == object_id
            )

    def all(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def verify_chain(self) -> bool:
        prior_hash = "GENESIS"
        for event in self.all():
            if event.prior_hash != prior_hash:
                return False
            event_base = {
                "sequence": event.sequence,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id,
                "actor_id": event.actor_id,
                "action": event.action,
                "object_type": event.object_type,
                "object_id": event.object_id,
                "payload": event.payload,
                "prior_hash": event.prior_hash,
            }
            if sha256_hex(event_base) != event.event_hash:
                return False
            prior_hash = event.event_hash
        return True


class FirestoreAuditLog(AuditLog):
    """Durable, transactionally sequenced audit chain for Cloud Run deployments."""

    def __init__(self, *, client=None, collection_prefix: str = "commonsgate") -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = client or firestore.Client()
        self._event_collection = self._client.collection(
            f"{collection_prefix}_audit_events"
        )
        self._head_reference = self._client.collection(
            f"{collection_prefix}_audit_meta"
        ).document("global_head")

    def append(
        self,
        *,
        correlation_id: str,
        actor_id: str,
        action: str,
        object_type: str,
        object_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        safe_payload = payload or {}
        prohibited = self.PROHIBITED_KEYS.intersection(safe_payload)
        if prohibited:
            raise ValueError(f"prohibited audit payload keys: {sorted(prohibited)}")
        transaction = self._client.transaction()

        @self._firestore.transactional
        def append_in_transaction(transaction) -> AuditEvent:
            head_snapshot = self._head_reference.get(transaction=transaction)
            head = (head_snapshot.to_dict() or {}) if head_snapshot.exists else {}
            sequence = int(head.get("sequence", 0)) + 1
            prior_hash = str(head.get("event_hash", "GENESIS"))
            timestamp = datetime.now(UTC)
            event_base = {
                "sequence": sequence,
                "timestamp": timestamp.isoformat(),
                "correlation_id": correlation_id,
                "actor_id": actor_id,
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "payload": safe_payload,
                "prior_hash": prior_hash,
            }
            event = AuditEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_hash=sha256_hex(event_base),
                sequence=sequence,
                timestamp=timestamp,
                correlation_id=correlation_id,
                actor_id=actor_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                payload=safe_payload,
                prior_hash=prior_hash,
            )
            transaction.create(
                self._event_collection.document(f"{sequence:020d}"),
                event.model_dump(mode="json"),
            )
            transaction.set(
                self._head_reference,
                {"sequence": sequence, "event_hash": event.event_hash},
            )
            return event

        return append_in_transaction(transaction)

    def list_for_object(self, object_id: str) -> tuple[AuditEvent, ...]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        values = [
            AuditEvent.model_validate(snapshot.to_dict())
            for snapshot in self._event_collection.where(
                filter=FieldFilter("object_id", "==", object_id)
            ).stream()
        ]
        return tuple(sorted(values, key=lambda event: event.sequence))

    def all(self) -> tuple[AuditEvent, ...]:
        values = [
            AuditEvent.model_validate(snapshot.to_dict())
            for snapshot in self._event_collection.stream()
        ]
        return tuple(sorted(values, key=lambda event: event.sequence))
