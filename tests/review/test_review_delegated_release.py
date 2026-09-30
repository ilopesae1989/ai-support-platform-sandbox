"""Delegated development release: provenance and data integrity, not model quality."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
from src.communication.contracts import CommunicationRequest, CommunicationResult
from src.review.contracts import REQUIRED_REVIEW_CRITERIA
from src.review.policy import build_review_request

ROOT = Path(__file__).resolve().parents[2]
BASE = 'tests/review/data/communication_review_v1.dev.jsonl'
DATA = 'tests/review/data/communication_review_v1.dev.delegated-r1.jsonl'
MANIFEST = 'docs/review/communication_review_v1_delegated_release_r1.json'
BASE_SHA = '9c7b2bd31364fcfb0400e2622908a0f2a9389a741bf7ce3cb9e02faf4ee9b3e3'
DATA_SHA = '307751f8465a16762397980e3f4a7c3f056fc16eb96c9dd1c07364c1130f74a5'

def _rows(path):
    return [json.loads(line) for line in (ROOT/path).read_text(encoding="utf-8").splitlines()]

def _manifest():
    return json.loads((ROOT/MANIFEST).read_text(encoding="utf-8"))

def test_release_and_original_have_exact_content_and_lineage():
    m = _manifest()
    assert hashlib.sha256((ROOT/BASE).read_bytes()).hexdigest() == BASE_SHA
    assert hashlib.sha256((ROOT/DATA).read_bytes()).hexdigest() == DATA_SHA
    assert m["source"]["baseline"] == {"path":BASE,"sha256":BASE_SHA}
    assert m["release"]["path"] == DATA and m["release"]["sha256"] == DATA_SHA
    for name in ("rubric", "instructions"):
        reference = m["source"][name]
        assert hashlib.sha256((ROOT/reference["path"]).read_bytes()).hexdigest() == reference["sha256"]

def test_only_declared_candidate_and_provenance_changes_are_present():
    original, released = _rows(BASE), _rows(DATA)
    expected = copy.deepcopy(original)
    for row in expected:
        row["label_status"] = "assistant_reviewed_user_delegated"
    assert expected[1]["case_id"] == "CR-DEV-002"
    expected[1]["candidate"]["details"][0] = expected[1]["context"]["technical_summary"]
    assert released == expected
    assert all(a["expectation"] == b["expectation"] for a,b in zip(original,released,strict=True))

def test_delegation_does_not_claim_human_or_independent_annotation():
    m = _manifest()
    assert m["authorization"]["type"] == "user_delegation"
    assert m["authorization"]["per_case_human_review_claimed"] is False
    a=m["adjudication"]
    assert a["performed_by"] == "assistant"
    assert a["individual_human_review"] is False and a["independent_semantic_validation"] is False
    assert a["production_quality_certified"] is False
    assert a["delegation_does_not_create_operational_HITL_approval"] is True
    assert all(d["individual_human_review"] is False for d in m["case_decisions"])

def test_partial_criteria_stay_partial_and_hypotheses_are_not_measurements():
    rows = _rows(DATA)
    assert len(rows)==24
    count=sum(len(r["expectation"]["criterion_outcomes"]) for r in rows)
    assert count==80 and 24*len(REQUIRED_REVIEW_CRITERIA)-count==88
    assert Counter(r["expectation"]["verdict"] for r in rows)=={"pass":8,"fail":12,"inconclusive":4}
    for row in rows:
        assert set(row["expectation"]["criterion_outcomes"]) <= set(REQUIRED_REVIEW_CRITERIA)
    rules = _manifest()["evaluation_rules"]
    assert rules["score_only_explicit_labels"] is True
    assert rules["fill_unlabeled_with_pass"] is False
    assert rules["global_case_verdicts_are_not_fully_adjudicated_ground_truth"] is True

def test_every_case_has_one_scoped_decision_matching_its_actual_labels():
    rows = _rows(DATA); decisions = _manifest()["case_decisions"]
    assert len(decisions)==24 and len({d["case_id"] for d in decisions})==24
    assert [d["case_id"] for d in decisions]==[r["case_id"] for r in rows]
    for row, decision in zip(rows,decisions,strict=True):
        assert decision["criterion_outcomes"]==row["expectation"]["criterion_outcomes"]
        assert decision["decision"]=="accepted_focal_labels_for_development"
        assert decision["case_verdict_is_hypothesis"] is True and decision["reason"].strip()

def test_all_released_inputs_still_validate_against_existing_domain_contracts():
    for row in _rows(DATA):
        context=CommunicationRequest.model_validate(row["context"])
        candidate=CommunicationResult.model_validate(row["candidate"])
        request=build_review_request(review_id="RELEASE-TYPE-CHECK",context=context,candidate=candidate)
        assert request.context.model_dump(mode="json")==row["context"]
        assert request.candidate.model_dump(mode="json")==row["candidate"]

def test_case_annotations_are_not_added_to_the_reviewer_request():
    for row in _rows(DATA):
        request=build_review_request(review_id="RELEASE-INPUT-CHECK",
            context=CommunicationRequest.model_validate(row["context"]),
            candidate=CommunicationResult.model_validate(row["candidate"]))
        data=request.model_dump(mode="json")
        assert set(data)=={"schema_version","review_id","criteria_version","context","candidate"}
        assert not ({"case_id","family","expectation","label_status","origin","split"} & set(data))

def test_release_is_development_only_and_preserves_the_base_plan():
    m=_manifest()
    assert all(r["split"]=="development" and r["origin"]=="synthetic" for r in _rows(DATA))
    assert m["release"]["split"]=="development"
    assert m["scope"]["original_corpus_preserved"] is True
    assert all(m["scope"][k] is False for k in ("model_invoked","holdout_created","runtime_wiring_changed","operational_HITL_changed","consumed_incidents_reused"))
    plan=m["plan_addendum"]
    assert hashlib.sha256((ROOT/plan["base_plan"]).read_bytes()).hexdigest()==plan["base_plan_sha256"]
    assert plan["effective_development_dataset"]==DATA
    assert m["evaluation_rules"]["development_results_are_not_holdout_or_production_certification"] is True
