"""Environment configuration with production guardrails."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    """Read a text setting without preserving secret-manager file newlines."""

    return os.getenv(name, default).strip()


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
    agent_a2a_url: str = "http://localhost:8081/a2a/commonsgate_agent"
    enable_cloud_trace: bool = False
    service_name: str = "commonsgate-api"
    service_revision: str = "local"

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
    def from_env(cls) -> Settings:
        return cls(
            environment=_env("COMMONSGATE_ENV", "development"),
            delegation_signing_secret=_env(
                "COMMONSGATE_DELEGATION_SECRET",
                "development-only-delegation-secret-32chars",
            ),
            admin_key=_env("COMMONSGATE_ADMIN_KEY", "development-only-admin-key"),
            normalizer_mode=_env("COMMONSGATE_NORMALIZER", "rule"),
            translator_mode=_env("COMMONSGATE_TRANSLATOR", "template"),
            repository_mode=_env("COMMONSGATE_REPOSITORY", "memory"),
            firestore_collection_prefix=_env(
                "COMMONSGATE_FIRESTORE_PREFIX", "commonsgate"
            ),
            public_base_url=_env(
                "COMMONSGATE_PUBLIC_BASE_URL", "http://localhost:8080"
            ),
            agent_a2a_url=_env(
                "COMMONSGATE_AGENT_A2A_URL",
                "http://localhost:8081/a2a/commonsgate_agent",
            ),
            enable_cloud_trace=_env(
                "COMMONSGATE_ENABLE_CLOUD_TRACE", "false"
            ).lower()
            in {"1", "true", "yes"},
            service_name=_env("K_SERVICE", "commonsgate-api"),
            service_revision=_env("K_REVISION", "local"),
        )
