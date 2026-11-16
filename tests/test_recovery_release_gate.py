from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.attestation.recovery_release_gate import REQUIRED_CHECKS, ReleaseEvidence, assess_legacy_cut

NOW = datetime(2026, 11, 12, 10, tzinfo=timezone.utc)
PIN = "a" * 64


def records():
    return [ReleaseEvidence(name, True, "NONLIVE" if name == "nonlive_full_exact_candidate" else "AZURE_EFFECTIVE",
        PIN, "b" * 64, "2026-11-12T09:59:00Z") for name in sorted(REQUIRED_CHECKS)]


def test_empty_evidence_never_opens_cut():
    decision = assess_legacy_cut([], candidate_sha256=PIN, now=NOW)
    assert not decision.ready_for_review and len(decision.failures) == len(REQUIRED_CHECKS)
    assert not decision.cut_executed and not decision.f27_accredited


@pytest.mark.parametrize("field,value", [("passed", False), ("passed", 1), ("environment", "NONLIVE"),
    ("candidate_sha256", "c" * 64), ("evidence_sha256", ""), ("observed_utc", "2026-11-11T09:59:00Z"),
    ("observed_utc", "2026-11-12T10:01:00Z")])
def test_incomplete_or_simulated_evidence_blocks_cut(field, value):
    evidence = records()
    index = next(i for i, e in enumerate(evidence) if e.check == "recovery_zero_sign_and_dispatch")
    evidence[index] = replace(evidence[index], **{field: value})
    assert not assess_legacy_cut(evidence, candidate_sha256=PIN, now=NOW).ready_for_review


def test_complete_inputs_only_prepare_review_do_not_execute_or_accredit():
    decision = assess_legacy_cut(records(), candidate_sha256=PIN, now=NOW)
    assert decision.ready_for_review and not decision.failures
    assert not decision.cut_executed and not decision.f27_accredited


def test_duplicate_evidence_is_not_additional_coverage():
    evidence = records()
    assert not assess_legacy_cut(evidence + evidence[:1], candidate_sha256=PIN, now=NOW).ready_for_review
