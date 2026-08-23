"""Canonical serialization and cryptographic commitments.

The allocation engine only hashes policy-relevant facts. Transport metadata such
as agent vendor, tier, retry count, and arrival time is deliberately excluded.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seed_commitment(seed: str) -> str:
    """Commit to a secret seed before the candidate manifest is frozen."""

    return sha256_hex({"domain": "commonsgate.seed.v1", "seed": seed})


def candidate_manifest_hash(candidates: Iterable[Mapping[str, Any]]) -> str:
    """Hash an order-independent, agent-blind allocation manifest."""

    ordered = sorted(candidates, key=lambda item: str(item["principal_token"]))
    return sha256_hex({"domain": "commonsgate.manifest.v1", "candidates": ordered})


def deterministic_rank(
    *, seed: str, manifest_hash: str, bucket: str, principal_token: str
) -> str:
    """Return a stable random-looking rank without using process-local RNG state."""

    return sha256_hex(
        {
            "domain": "commonsgate.rank.v1",
            "seed": seed,
            "manifest_hash": manifest_hash,
            "bucket": bucket,
            "principal_token": principal_token,
        }
    )
