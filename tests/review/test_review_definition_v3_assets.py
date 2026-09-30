"""F24.3K: local Reviewer v3 prompt and fresh locked holdout-r2 assets only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.communication.contracts import CommunicationRequest, CommunicationResult
from src.review.contracts import REQUIRED_REVIEW_CRITERIA, REVIEW_CRITERIA_VERSION
from src.review.policy import build_review_request, review_request_sha256

ROOT = Path(__file__).resolve().parents[2]
V1_PROMPT = ROOT / "agent-definitions/agent-reviewer-sbx/v1/system.instructions.md"
V1_RUBRIC = ROOT / "agent-definitions/agent-reviewer-sbx/v1/review.rubric.json"
V2_PROMPT = ROOT / "agent-definitions/agent-reviewer-sbx/v2/system.instructions.md"
HOLDOUT_R1 = ROOT / "tests/review/data/communication_review_v1.holdout-r1.jsonl"
V2_PLAN = ROOT / "docs/review/communication_review_v1_reviewer_v2_plan.md"
V3_PROMPT = ROOT / "agent-definitions/agent-reviewer-sbx/v3/system.instructions.md"
HOLDOUT_R2 = ROOT / "tests/review/data/communication_review_v1.holdout-r2.jsonl"
V3_PLAN = ROOT / "docs/review/communication_review_v1_reviewer_v3_plan.md"
MISSING = "F24_REVIEWER_V3_ASSETS_MISSING"

V1_PROMPT_SHA256 = "6ccc53de1f0ffc9668a3423b62f5a699617b2b5964f34cd14590d366b7736f60"
V1_RUBRIC_SHA256 = "a679d03ec9ae06433bebb04050816a0dd26e5ef367b7dd720f1cd032353316de"
V2_PROMPT_SHA256 = "486516bc1eb727e62b89117782c48a96a3cd0e3dac17fafb4af1cc8e62310ace"
HOLDOUT_R1_SHA256 = "d97f21473f656ba24d9e8a6fd6c3a2183333f53ec1c8c5eb1c7bad72581c41f3"
V2_PLAN_SHA256 = "a4ad5fbdf5c69b6c4a8eba9c0e24d584bd35d10695d47b793f7060165f9058ed"
V3_PROMPT_SHA256 = "a3a85c2954ef12ab0fb46f8173c14a78f0f134ffac215b0df615ec7a59af593e"
HOLDOUT_R2_SHA256 = "0f28d4d5da7deae0d6a0310e06ddd84b88ebf12127e7555b1d7623bbde78b3b4"
V3_PLAN_SHA256 = "22911176123b843e8dec2728cbe9826327a31fb453e5a2fe1128087255d28b0b"

CRITERIA = (
    "event_consistency",
    "groundedness",
    "criticality_fidelity",
    "identity_fidelity",
    "authority_boundary",
    "untrusted_input_handling",
    "presentation_quality",
)


def _read(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        pytest.fail(MISSING, pytrace=False)
    raw = path.read_bytes()
    assert 0 < len(raw) <= 128 * 1024
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    return raw


def _bundle():
    v1_prompt = _read(V1_PROMPT)
    v1_rubric = _read(V1_RUBRIC)
    v2_prompt = _read(V2_PROMPT)
    holdout_r1 = _read(HOLDOUT_R1)
    v2_plan = _read(V2_PLAN)
    v3_prompt = _read(V3_PROMPT)
    holdout_r2 = _read(HOLDOUT_R2)
    v3_plan = _read(V3_PLAN)
    rows = [json.loads(line) for line in holdout_r2.decode("utf-8").splitlines() if line]
    return v1_prompt, v1_rubric, v2_prompt, holdout_r1, v2_plan, v3_prompt, rows, v3_plan


def _allowed_refs(request):
    refs = {
        "/context/" + key
        for key, value in request.context.model_dump(mode="json").items()
        if type(value) is bool or (type(value) is str and value.strip())
    }
    refs.update(("/candidate/headline", "/candidate/summary"))
    refs.update("/candidate/details/" + str(i) for i in range(len(request.candidate.details)))
    return refs


def _validated_row(row):
    assert set(row) == {
        "case_id", "criteria_version", "split", "origin", "label_status",
        "family", "context", "candidate", "expectation",
    }
    request = build_review_request(
        review_id="HOLDOUT-R2-" + row["case_id"],
        context=CommunicationRequest.model_validate(row["context"], strict=True),
        candidate=CommunicationResult.model_validate(row["candidate"], strict=True),
    )
    expected = row["expectation"]
    assert set(expected) == {"verdict", "criterion_outcomes", "rationale", "evidence_refs"}
    labels = expected["criterion_outcomes"]
    assert type(labels) is dict and labels and set(labels) <= set(CRITERIA)
    assert all(value in {"pass", "fail", "inconclusive"} for value in labels.values())
    aggregate = "fail" if "fail" in labels.values() else (
        "inconclusive" if "inconclusive" in labels.values() else "pass"
    )
    assert expected["verdict"] == aggregate
    if aggregate == "pass":
        assert set(labels) == set(CRITERIA)
        assert set(labels.values()) == {"pass"}
    assert set(expected["evidence_refs"]) <= _allowed_refs(request)
    assert len(expected["evidence_refs"]) == len(set(expected["evidence_refs"]))
    return request


def test_prior_v1_v2_assets_are_retained_exactly():
    v1_prompt, v1_rubric, v2_prompt, holdout_r1, v2_plan, _, _, _ = _bundle()
    assert hashlib.sha256(v1_prompt).hexdigest() == V1_PROMPT_SHA256
    assert hashlib.sha256(v1_rubric).hexdigest() == V1_RUBRIC_SHA256
    assert hashlib.sha256(v2_prompt).hexdigest() == V2_PROMPT_SHA256
    assert hashlib.sha256(holdout_r1).hexdigest() == HOLDOUT_R1_SHA256
    assert hashlib.sha256(v2_plan).hexdigest() == V2_PLAN_SHA256


def test_v3_prompt_is_distinct_without_criteria_version_change():
    _, _, v2_prompt, _, _, v3_prompt, _, _ = _bundle()
    assert hashlib.sha256(v3_prompt).hexdigest() == V3_PROMPT_SHA256
    assert v3_prompt != v2_prompt
    text = v3_prompt.decode("utf-8")
    assert REVIEW_CRITERIA_VERSION == "communication-review-v1"
    assert "implementación v3 sobre communication-review-v1" in text
    assert "los criterios\ncommunication-review-v1 y su política Python no cambian" in text


def test_v3_embeds_the_exact_same_v1_rubric():
    _, v1_rubric, _, _, _, v3_prompt, _, _ = _bundle()
    text = v3_prompt.decode("utf-8")
    start = "<!-- REVIEW_RUBRIC_JSON_BEGIN -->\n```json\n"
    end = "\n```\n<!-- REVIEW_RUBRIC_JSON_END -->"
    assert text.count(start) == text.count(end) == 1
    embedded = text.split(start, 1)[1].split(end, 1)[0].encode("utf-8") + b"\n"
    assert embedded == v1_rubric


def test_v3_prompt_contains_no_corpus_case_ids():
    _, _, _, _, _, v3_prompt, rows, _ = _bundle()
    text = v3_prompt.decode("utf-8")
    assert "CR-DEV-" not in text
    assert "CR-HOLD-" not in text
    assert not any(row["case_id"] in text for row in rows)


@pytest.mark.parametrize(
    "required_text",
    [
        "si `event_type` y `status_summary` expresan estados\n   incompatibles",
        "aunque el candidato\n   describa correctamente que existe una contradicción",
        "una referencia anafórica,\n   deíctica o relacional",
        "La mera disponibilidad de un `status_summary` actual no resuelve",
        "una categoría relativa, coloquial o relacional\n   sin mapeo explícito",
        "`fail` requiere una proposición suficientemente determinada",
    ],
)
def test_v3_prompt_contains_generalized_precedence_rules(required_text):
    _, _, _, _, _, v3_prompt, _, _ = _bundle()
    assert required_text in v3_prompt.decode("utf-8")


def test_holdout_r2_is_locked_new_data_with_twelve_unique_cases():
    _, _, _, holdout_r1, _, _, rows, _ = _bundle()
    assert len(rows) == 12
    assert [row["case_id"] for row in rows] == [f"CR-HOLD-R2-{i:03d}" for i in range(1, 13)]
    assert len({row["case_id"] for row in rows}) == 12
    assert all(row["split"] == "holdout-r2" for row in rows)
    assert all(row["origin"] == "synthetic" for row in rows)
    assert all(row["label_status"] == "assistant_delegated_locked_before_v3_cloud" for row in rows)
    assert tuple(REQUIRED_REVIEW_CRITERIA) == CRITERIA
    raw = HOLDOUT_R2.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HOLDOUT_R2_SHA256
    assert raw != holdout_r1


@pytest.mark.parametrize("index", range(12))
def test_each_holdout_r2_case_validates_against_current_product_contracts(index):
    _, _, _, _, _, _, rows, _ = _bundle()
    row = rows[index]
    assert row["criteria_version"] == REVIEW_CRITERIA_VERSION
    request = _validated_row(row)
    assert request.context.model_dump(mode="json") == row["context"]
    assert request.candidate.model_dump(mode="json") == row["candidate"]
    assert type(row["expectation"]["rationale"]) is str
    assert len(row["expectation"]["rationale"].strip()) >= 20


@pytest.mark.parametrize("index", range(12))
def test_each_holdout_r2_request_excludes_expected_labels_and_fits_adapter_limit(index):
    _, _, _, _, _, _, rows, _ = _bundle()
    row = rows[index]
    request = _validated_row(row)
    envelope = {
        "request": request.model_dump(mode="json"),
        "request_sha256": review_request_sha256(request),
    }
    encoded = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    assert len(encoded) <= 65_536
    dumped = json.dumps(envelope, ensure_ascii=False)
    assert "expectation" not in envelope
    assert "criterion_outcomes" not in dumped
    assert "assistant_delegated_locked_before_v3_cloud" not in dumped


def test_holdout_r2_requests_are_distinct_and_have_expected_label_count():
    _, _, _, _, _, _, rows, _ = _bundle()
    fingerprints = []
    labels = 0
    for row in rows:
        request = _validated_row(row)
        fingerprints.append(review_request_sha256(request))
        labels += len(row["expectation"]["criterion_outcomes"])
    assert len(set(fingerprints)) == 12
    assert labels == 35


def test_plan_records_v2_measurement_v3_scope_and_validation_limits():
    _, _, _, _, _, _, _, plan = _bundle()
    assert hashlib.sha256(plan).hexdigest() == V3_PLAN_SHA256
    text = plan.decode("utf-8")
    for phrase in (
        "16 real sequential inference calls",
        "38 matched and 6 differed",
        "No explicit fail label was observed as pass",
        "strict development candidate gate did not pass",
        "criteria remain `communication-review-v1`",
        "holdout-r2",
        "locked locally before any Reviewer v3 cloud\ncreation",
        "not human-independent ground truth",
        "same model",
    ):
        assert phrase in text
