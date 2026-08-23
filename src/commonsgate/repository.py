"""Authoritative storage port and in-memory development adapter."""

from __future__ import annotations

import threading
from typing import Protocol

from .canonical import sha256_hex
from .contracts import AppealRecord, AppealStatus, RequestStatus, RoundRecord, StoredRequest
from .errors import CommonsGateError


class Repository(Protocol):
    def create_round(self, round_record: RoundRecord) -> None: ...
    def get_round(self, round_id: str) -> RoundRecord: ...
    def save_round(self, round_record: RoundRecord) -> None: ...
    def create_request(self, request: StoredRequest) -> None: ...
    def save_request(self, request: StoredRequest) -> None: ...
    def get_request(self, request_id: str) -> StoredRequest: ...
    def find_principal_request(
        self, program_id: str, round_id: str, principal_token: str
    ) -> StoredRequest | None: ...
    def list_round_requests(
        self, round_id: str, status: RequestStatus | None = None
    ) -> tuple[StoredRequest, ...]: ...
    def create_appeal(self, appeal: AppealRecord) -> None: ...
    def get_appeal(self, appeal_id: str) -> AppealRecord: ...
    def save_appeal(self, appeal: AppealRecord) -> None: ...
    def list_round_appeals(
        self, round_id: str, status: AppealStatus | None = None
    ) -> tuple[AppealRecord, ...]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._rounds: dict[str, RoundRecord] = {}
        self._requests: dict[str, StoredRequest] = {}
        self._principal_index: dict[tuple[str, str, str], str] = {}
        self._appeals: dict[str, AppealRecord] = {}
        self._lock = threading.RLock()

    def create_round(self, round_record: RoundRecord) -> None:
        with self._lock:
            if round_record.round_id in self._rounds:
                raise CommonsGateError(
                    "ROUND_EXISTS", "The round already exists.", status_code=409
                )
            self._rounds[round_record.round_id] = round_record.model_copy(deep=True)

    def get_round(self, round_id: str) -> RoundRecord:
        with self._lock:
            try:
                return self._rounds[round_id].model_copy(deep=True)
            except KeyError as exc:
                raise CommonsGateError(
                    "ROUND_NOT_FOUND", "The round was not found.", status_code=404
                ) from exc

    def save_round(self, round_record: RoundRecord) -> None:
        with self._lock:
            if round_record.round_id not in self._rounds:
                raise CommonsGateError(
                    "ROUND_NOT_FOUND", "The round was not found.", status_code=404
                )
            self._rounds[round_record.round_id] = round_record.model_copy(deep=True)

    def create_request(self, request: StoredRequest) -> None:
        key = (request.program_id, request.round_id, request.principal_token)
        with self._lock:
            if request.request_id in self._requests:
                raise CommonsGateError(
                    "REQUEST_EXISTS", "The request already exists.", status_code=409
                )
            if key in self._principal_index:
                raise CommonsGateError(
                    "PRINCIPAL_REQUEST_EXISTS",
                    "An active request already exists.",
                    status_code=409,
                )
            self._requests[request.request_id] = request.model_copy(deep=True)
            self._principal_index[key] = request.request_id

    def save_request(self, request: StoredRequest) -> None:
        with self._lock:
            if request.request_id not in self._requests:
                raise CommonsGateError(
                    "REQUEST_NOT_FOUND", "The request was not found.", status_code=404
                )
            self._requests[request.request_id] = request.model_copy(deep=True)

    def get_request(self, request_id: str) -> StoredRequest:
        with self._lock:
            try:
                return self._requests[request_id].model_copy(deep=True)
            except KeyError as exc:
                raise CommonsGateError(
                    "REQUEST_NOT_FOUND", "The request was not found.", status_code=404
                ) from exc

    def find_principal_request(
        self, program_id: str, round_id: str, principal_token: str
    ) -> StoredRequest | None:
        with self._lock:
            request_id = self._principal_index.get(
                (program_id, round_id, principal_token)
            )
            return (
                self._requests[request_id].model_copy(deep=True) if request_id else None
            )

    def list_round_requests(
        self, round_id: str, status: RequestStatus | None = None
    ) -> tuple[StoredRequest, ...]:
        with self._lock:
            values = [
                request
                for request in self._requests.values()
                if request.round_id == round_id
            ]
            if status is not None:
                values = [request for request in values if request.status == status]
            return tuple(
                request.model_copy(deep=True)
                for request in sorted(values, key=lambda item: item.request_id)
            )

    def create_appeal(self, appeal: AppealRecord) -> None:
        with self._lock:
            if appeal.appeal_id in self._appeals:
                raise CommonsGateError(
                    "APPEAL_EXISTS", "The appeal already exists.", status_code=409
                )
            if any(
                item.request_id == appeal.request_id
                and item.status == AppealStatus.PENDING
                for item in self._appeals.values()
            ):
                raise CommonsGateError(
                    "APPEAL_ALREADY_PENDING",
                    "This request already has a pending appeal.",
                    status_code=409,
                )
            self._appeals[appeal.appeal_id] = appeal.model_copy(deep=True)

    def get_appeal(self, appeal_id: str) -> AppealRecord:
        with self._lock:
            try:
                return self._appeals[appeal_id].model_copy(deep=True)
            except KeyError as exc:
                raise CommonsGateError(
                    "APPEAL_NOT_FOUND", "The appeal was not found.", status_code=404
                ) from exc

    def save_appeal(self, appeal: AppealRecord) -> None:
        with self._lock:
            if appeal.appeal_id not in self._appeals:
                raise CommonsGateError(
                    "APPEAL_NOT_FOUND", "The appeal was not found.", status_code=404
                )
            self._appeals[appeal.appeal_id] = appeal.model_copy(deep=True)

    def list_round_appeals(
        self, round_id: str, status: AppealStatus | None = None
    ) -> tuple[AppealRecord, ...]:
        with self._lock:
            values = [
                appeal for appeal in self._appeals.values() if appeal.round_id == round_id
            ]
            if status is not None:
                values = [appeal for appeal in values if appeal.status == status]
            return tuple(
                appeal.model_copy(deep=True)
                for appeal in sorted(values, key=lambda item: item.appeal_id)
            )


class FirestoreRepository:
    """Google Cloud Firestore adapter for authoritative deployment state."""

    def __init__(self, *, client=None, collection_prefix: str = "commonsgate") -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = client or firestore.Client()
        self._rounds = self._client.collection(f"{collection_prefix}_rounds")
        self._requests = self._client.collection(f"{collection_prefix}_requests")
        self._principal_index = self._client.collection(
            f"{collection_prefix}_principal_requests"
        )
        self._appeals = self._client.collection(f"{collection_prefix}_appeals")

    @staticmethod
    def _dump(model) -> dict:
        return model.model_dump(mode="json")

    @staticmethod
    def _missing(code: str, message: str) -> CommonsGateError:
        return CommonsGateError(code, message, status_code=404)

    def create_round(self, round_record: RoundRecord) -> None:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._rounds.document(round_record.round_id).create(
                self._dump(round_record)
            )
        except AlreadyExists as exc:
            raise CommonsGateError(
                "ROUND_EXISTS", "The round already exists.", status_code=409
            ) from exc

    def get_round(self, round_id: str) -> RoundRecord:
        snapshot = self._rounds.document(round_id).get()
        if not snapshot.exists:
            raise self._missing("ROUND_NOT_FOUND", "The round was not found.")
        return RoundRecord.model_validate(snapshot.to_dict())

    def save_round(self, round_record: RoundRecord) -> None:
        reference = self._rounds.document(round_record.round_id)
        if not reference.get().exists:
            raise self._missing("ROUND_NOT_FOUND", "The round was not found.")
        reference.set(self._dump(round_record))

    @staticmethod
    def _principal_key(program_id: str, round_id: str, principal_token: str) -> str:
        return sha256_hex(
            {
                "domain": "commonsgate.principal-index.v1",
                "program_id": program_id,
                "round_id": round_id,
                "principal_token": principal_token,
            }
        )

    def create_request(self, request: StoredRequest) -> None:
        from google.api_core.exceptions import AlreadyExists

        request_reference = self._requests.document(request.request_id)
        index_reference = self._principal_index.document(
            self._principal_key(
                request.program_id, request.round_id, request.principal_token
            )
        )
        transaction = self._client.transaction()

        @self._firestore.transactional
        def create_in_transaction(transaction):
            if index_reference.get(transaction=transaction).exists:
                return False
            transaction.create(request_reference, self._dump(request))
            transaction.create(
                index_reference,
                {
                    "request_id": request.request_id,
                    "program_id": request.program_id,
                    "round_id": request.round_id,
                },
            )
            return True

        try:
            created = create_in_transaction(transaction)
        except AlreadyExists as exc:
            raise CommonsGateError(
                "REQUEST_EXISTS", "The request already exists.", status_code=409
            ) from exc
        if not created:
            raise CommonsGateError(
                "PRINCIPAL_REQUEST_EXISTS",
                "An active request already exists.",
                status_code=409,
            )

    def save_request(self, request: StoredRequest) -> None:
        reference = self._requests.document(request.request_id)
        if not reference.get().exists:
            raise self._missing("REQUEST_NOT_FOUND", "The request was not found.")
        reference.set(self._dump(request))

    def get_request(self, request_id: str) -> StoredRequest:
        snapshot = self._requests.document(request_id).get()
        if not snapshot.exists:
            raise self._missing("REQUEST_NOT_FOUND", "The request was not found.")
        return StoredRequest.model_validate(snapshot.to_dict())

    def find_principal_request(
        self, program_id: str, round_id: str, principal_token: str
    ) -> StoredRequest | None:
        index = self._principal_index.document(
            self._principal_key(program_id, round_id, principal_token)
        ).get()
        if not index.exists:
            return None
        return self.get_request(index.to_dict()["request_id"])

    def list_round_requests(
        self, round_id: str, status: RequestStatus | None = None
    ) -> tuple[StoredRequest, ...]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._requests.where(filter=FieldFilter("round_id", "==", round_id))
        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))
        values = [
            StoredRequest.model_validate(snapshot.to_dict())
            for snapshot in query.stream()
        ]
        return tuple(sorted(values, key=lambda item: item.request_id))

    def create_appeal(self, appeal: AppealRecord) -> None:
        from google.api_core.exceptions import AlreadyExists
        from google.cloud.firestore_v1.base_query import FieldFilter

        pending = list(
            self._appeals.where(
                filter=FieldFilter("request_id", "==", appeal.request_id)
            )
            .where(filter=FieldFilter("status", "==", AppealStatus.PENDING.value))
            .limit(1)
            .stream()
        )
        if pending:
            raise CommonsGateError(
                "APPEAL_ALREADY_PENDING",
                "This request already has a pending appeal.",
                status_code=409,
            )
        try:
            self._appeals.document(appeal.appeal_id).create(self._dump(appeal))
        except AlreadyExists as exc:
            raise CommonsGateError(
                "APPEAL_EXISTS", "The appeal already exists.", status_code=409
            ) from exc

    def get_appeal(self, appeal_id: str) -> AppealRecord:
        snapshot = self._appeals.document(appeal_id).get()
        if not snapshot.exists:
            raise self._missing("APPEAL_NOT_FOUND", "The appeal was not found.")
        return AppealRecord.model_validate(snapshot.to_dict())

    def save_appeal(self, appeal: AppealRecord) -> None:
        reference = self._appeals.document(appeal.appeal_id)
        if not reference.get().exists:
            raise self._missing("APPEAL_NOT_FOUND", "The appeal was not found.")
        reference.set(self._dump(appeal))

    def list_round_appeals(
        self, round_id: str, status: AppealStatus | None = None
    ) -> tuple[AppealRecord, ...]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._appeals.where(filter=FieldFilter("round_id", "==", round_id))
        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))
        values = [
            AppealRecord.model_validate(snapshot.to_dict())
            for snapshot in query.stream()
        ]
        return tuple(sorted(values, key=lambda item: item.appeal_id))
