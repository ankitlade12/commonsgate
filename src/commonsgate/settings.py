"""Environment configuration with production guardrails."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    delegation_signing_secret: str = "development-only-delegation-secret-32chars"
    admin_key: str = "development-only-admin-key"
    normalizer_mode: str = "rule"
    translator_mode: str = "template"
    repository_mode: str = "memory"
    firestore_collection_prefix: str = "commonsgate"
    public_base_url: str = "http://localhost:8080"
    enable_cloud_trace: bool = False
    service_name: str = "commonsgate-api"

    def __post_init__(self) -> None:
        if self.environment == "production":
            if self.delegation_signing_secret.startswith("development-"):
                raise ValueError(
                    "production requires a non-default delegation signing secret"
                )
            if self.admin_key.startswith("development-"):
                raise ValueError("production requires a non-default admin key")
            if self.normalizer_mode != "gemini":
                raise ValueError("production requires COMMONSGATE_NORMALIZER=gemini")
            if self.repository_mode != "firestore":
                raise ValueError("production requires COMMONSGATE_REPOSITORY=firestore")
        if self.repository_mode not in {"memory", "firestore"}:
            raise ValueError("COMMONSGATE_REPOSITORY must be 'memory' or 'firestore'")
        if self.translator_mode not in {"template", "gemini"}:
            raise ValueError("COMMONSGATE_TRANSLATOR must be 'template' or 'gemini'")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("COMMONSGATE_ENV", "development"),
            delegation_signing_secret=os.getenv(
                "COMMONSGATE_DELEGATION_SECRET",
                "development-only-delegation-secret-32chars",
            ),
            admin_key=os.getenv("COMMONSGATE_ADMIN_KEY", "development-only-admin-key"),
            normalizer_mode=os.getenv("COMMONSGATE_NORMALIZER", "rule"),
            translator_mode=os.getenv("COMMONSGATE_TRANSLATOR", "template"),
            repository_mode=os.getenv("COMMONSGATE_REPOSITORY", "memory"),
            firestore_collection_prefix=os.getenv(
                "COMMONSGATE_FIRESTORE_PREFIX", "commonsgate"
            ),
            public_base_url=os.getenv(
                "COMMONSGATE_PUBLIC_BASE_URL", "http://localhost:8080"
            ),
            enable_cloud_trace=os.getenv(
                "COMMONSGATE_ENABLE_CLOUD_TRACE", "false"
            ).lower()
            in {"1", "true", "yes"},
            service_name=os.getenv("K_SERVICE", "commonsgate-api"),
        )
