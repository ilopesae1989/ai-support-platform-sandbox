"""Explicit release gate for recovery and a reversible legacy revision cut.

This gate evaluates independently collected evidence; it does not collect Azure
facts, execute a cut, approve tools or turn offline tests into LIVE evidence.
Any absent, stale or mixed-build evidence keeps the cut closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re


REQUIRED_CHECKS = frozenset({
    "read_native_approval_and_execution", "write_native_approval_and_execution",
    "read_sign_own_key", "write_sign_own_key", "attestor_sign_own_key",
    "read_cannot_sign_write_or_attestor", "write_cannot_sign_read_or_attestor",
    "attestor_cannot_sign_backends", "anonymous_and_wrong_audience_rejected",
    "wrong_role_rejected_before_dispatch", "governor_outbox_only_core_can_insert",
    "attestor_host_independent", "sql_journal_and_index_actual_readback",
    "blob_actual_readback_and_locked_policy", "recovery_zero_sign_and_dispatch",
    "checkpoint_replay_cannot_redispatch", "uncertain_commit_cannot_redispatch",
    "selected_publications_no_legacy_reference", "new_route_observation_window",
    "nonlive_full_exact_candidate", "rollback_revision_healthy_and_pinned",
})


@dataclass(frozen=True)
class ReleaseEvidence:
    check: str
    passed: bool
    environment: str
    candidate_sha256: str
    evidence_sha256: str
    observed_utc: str


@dataclass(frozen=True)
class LegacyCutDecision:
    ready_for_review: bool
    failures: tuple[str, ...]
    cut_executed: bool = False
    f27_accredited: bool = False


def assess_legacy_cut(records, *, candidate_sha256, now, max_age_seconds=3600):
    if (not re.fullmatch(r"[a-f0-9]{64}", candidate_sha256) or not isinstance(now, datetime)
            or now.tzinfo is None or type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600):
        raise ValueError("Pinned candidate, UTC clock and bounded evidence age required")
    records = tuple(records)
    failures = []
    by_check = {}
    for record in records:
        if type(record) is not ReleaseEvidence or record.check not in REQUIRED_CHECKS:
            failures.append("UNRECOGNIZED_EVIDENCE")
            continue
        if record.check in by_check:
            failures.append("DUPLICATE_" + record.check)
        by_check[record.check] = record
        if record.passed is not True:
            failures.append("FAILED_" + record.check)
        expected = "NONLIVE" if record.check == "nonlive_full_exact_candidate" else "AZURE_EFFECTIVE"
        if record.environment != expected:
            failures.append("WRONG_EVIDENCE_ENVIRONMENT_" + record.check)
        if record.candidate_sha256 != candidate_sha256 or not re.fullmatch(r"[a-f0-9]{64}", record.evidence_sha256):
            failures.append("PIN_OR_DIGEST_" + record.check)
        try:
            observed = datetime.fromisoformat(record.observed_utc.replace("Z", "+00:00"))
            if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= max_age_seconds:
                raise ValueError("stale")
        except (TypeError, ValueError):
            failures.append("STALE_" + record.check)
    failures.extend("MISSING_" + name for name in sorted(REQUIRED_CHECKS - by_check.keys()))
    return LegacyCutDecision(not failures, tuple(failures))
