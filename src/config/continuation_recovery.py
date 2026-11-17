"""Strict, opt-in recovery configuration supplied by the deployment host."""
from collections.abc import Mapping
import json

from src.runtime.incident_continuation_recovery_runner import ContinuationRecoveryPolicy


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate recovery configuration field.")
        result[key] = value
    return result


def parse_continuation_recovery_policy(environment: Mapping) -> ContinuationRecoveryPolicy | None:
    if not isinstance(environment, Mapping):
        raise TypeError("Recovery configuration requires a mapping.")
    if "CONTINUATION_RECOVERY_JSON" not in environment:
        return None
    raw = environment["CONTINUATION_RECOVERY_JSON"]
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("CONTINUATION_RECOVERY_JSON must be nonempty JSON.")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        raise ValueError("Invalid CONTINUATION_RECOVERY_JSON.") from None
    if (not isinstance(value, dict) or value.get("schema") != "continuation-recovery-v1"
            or type(value.get("enabled")) is not bool):
        raise ValueError("Recovery schema and explicit boolean enabled are required.")
    fields = {"schema", "enabled"}
    if not value["enabled"]:
        if set(value) != fields:
            raise ValueError("Disabled recovery only accepts schema and enabled.")
        return None
    policy_fields = {"min_claim_age_seconds", "interval_seconds", "batch_size", "max_batches_per_cycle"}
    if set(value) != fields | policy_fields:
        raise ValueError("Enabled recovery requires all policy fields and no unknown fields.")
    return ContinuationRecoveryPolicy(**{key: value[key] for key in policy_fields})
