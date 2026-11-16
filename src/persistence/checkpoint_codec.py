"""Application boundary for the pinned MAF checkpoint JSON format.

Version 1.0 is the existing WorkflowCheckpoint version, not an SDK version.
The wire format stays unchanged. Decode only trusted persistence; an allowlist
does not make external pickle-bearing input safe.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from agent_framework import WorkflowCheckpoint, WorkflowCheckpointException
from agent_framework._workflows._checkpoint_encoding import (
    decode_checkpoint_value, encode_checkpoint_value,
)

CHECKPOINT_FORMAT_VERSION = "1.0"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkflowCheckpointException("Duplicate checkpoint JSON key.")
        result[key] = value
    return result


def _require_supported_version(encoded) -> None:
    if not isinstance(encoded, dict) or encoded.get("version") != CHECKPOINT_FORMAT_VERSION:
        raise WorkflowCheckpointException("Unsupported checkpoint format version.")


@dataclass(frozen=True, kw_only=True)
class WorkflowCheckpointCodec:
    allowed_types: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_types, frozenset) or any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in self.allowed_types
        ):
            raise TypeError("allowed_types must be an explicit frozenset of exact type names.")

    def encode(self, checkpoint: WorkflowCheckpoint) -> str:
        if not isinstance(checkpoint, WorkflowCheckpoint):
            raise TypeError("checkpoint must be WorkflowCheckpoint.")
        data = checkpoint.to_dict()
        _require_supported_version(data)
        encoded = encode_checkpoint_value(data)
        payload = json.dumps(encoded, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        # Refuse to persist state this same reader cannot restore.
        self.decode(payload)
        return payload

    def decode(self, payload: str) -> WorkflowCheckpoint:
        if not isinstance(payload, str):
            raise TypeError("Checkpoint payload must be str.")
        try:
            encoded = json.loads(payload, object_pairs_hook=_unique_object)
        except (ValueError, TypeError) as exc:
            raise WorkflowCheckpointException("Invalid checkpoint JSON.") from exc
        # Check before the SDK decoder can reconstruct any nested object.
        _require_supported_version(encoded)
        decoded = decode_checkpoint_value(encoded, allowed_types=self.allowed_types)
        return WorkflowCheckpoint.from_dict(decoded)
