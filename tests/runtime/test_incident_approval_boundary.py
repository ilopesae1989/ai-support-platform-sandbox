from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import src.runtime.incident_approval_processor as processor
import src.runtime.procedure.approval_evidence as evidence
from src.channels.teams import approval_evidence as teams_evidence
from src.channels.teams.approval_context import to_authorized_approval_context
from src.communication.checkpoint_recovery import CommunicationCheckpointRecoveryError
from src.communication.context_state import SAFE_COMMUNICATION_CONTEXT_STATE_KEY
from src.runtime.procedure.approval_context import AuthorizedApprovalContext
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_resumer import ApprovalResumeMismatchError
from src.runtime.procedure.approval_store import ApprovalAlreadyConsumedError, SqlitePendingApprovalStore
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from tests.channels.teams.test_approval_evidence_from_request import (
    create_authorized_invocation, create_restored_request,
)
from tests.runtime._neutral_incident_case import decision_context, prepare_native_case


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_historical_evidence_json_remains_identical(monkeypatch, decision):
    fixture = json.loads((ROOT / "tests/fixtures/approvals/evidence_before_e3_p3.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(evidence, "utc_now", lambda: datetime(2026, 11, 16, 16, 0, tzinfo=timezone.utc))
    request = create_restored_request()
    invocation = create_authorized_invocation(request, decision=decision)
    result = teams_evidence.build_teams_approval_evidence_from_request(invocation=invocation, request=request)
    assert result.model_dump(mode="json") == fixture[decision]
    assert type(result) is evidence.ApprovalDecisionEvidence


def test_legacy_evidence_import_resolves_to_canonical_runtime_contract():
    assert teams_evidence.ApprovalDecisionEvidence is evidence.ApprovalDecisionEvidence
    assert teams_evidence.TeamsApprovalEvidenceError is evidence.ApprovalEvidenceError


def test_teams_mapping_preserves_identity_policy_and_action():
    invocation = create_authorized_invocation(create_restored_request())
    context = to_authorized_approval_context(invocation)
    assert context.action is invocation.action
    assert context.policy_id == invocation.policy_id
    assert context.identity.model_dump() == {
        "channel": "msteams", "identity_scheme": "microsoft_entra_object_id",
        "tenant_id": invocation.operator.tenant_id,
        "principal_id": invocation.operator.aad_object_id,
        "conversation_id": invocation.operator.conversation_id,
        "channel_user_id": invocation.operator.teams_user_id,
        "display_name": invocation.operator.display_name,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["dict", "object", "base-model", "channel-model"])
async def test_core_rejects_unmapped_input_before_accessing_dependencies(kind):
    original = create_authorized_invocation(create_restored_request())
    bad = {
        "dict": original.model_dump(), "object": object(),
        "base-model": AuthorizedApprovalInvocation(policy_id=original.policy_id, action=original.action),
        "channel-model": original,
    }[kind]
    with pytest.raises(TypeError, match="AuthorizedApprovalContext"):
        await processor.process_authorized_incident_approval(
            invocation=bad, store=object(), workflow=object(), checkpoint_storage=object(),
        )


@pytest.mark.parametrize("field", ["tenant_id", "principal_id", "conversation_id", "policy_id"])
def test_neutral_context_rejects_ambiguous_identity(field):
    values = to_authorized_approval_context(create_authorized_invocation(create_restored_request())).model_dump()
    if field == "policy_id":
        values[field] = " policy "
    else:
        values["identity"][field] = " identity "
    with pytest.raises(ValidationError):
        AuthorizedApprovalContext.model_validate(values)


@pytest.mark.parametrize("field,value", [
    ("workflow_id", ""), ("approval_id", "different"),
    ("conversation_id", "different"), ("conversation_id", None),
], ids=["missing-workflow", "wrong-approval", "wrong-conversation", "missing-conversation"])
def test_neutral_evidence_requires_the_restored_request_identity(field, value):
    request = create_restored_request()
    context = decision_context(request)
    with pytest.raises(evidence.ApprovalEvidenceError):
        evidence.build_approval_evidence_from_request(invocation=context, request=replace(request, **{field: value}))


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_native_incident_continuation_preserves_consumption_and_blocks_replay(tmp_path, decision):
    case = await prepare_native_case(tmp_path)
    context = decision_context(case.request, decision)
    result = await processor.process_authorized_incident_approval(
        invocation=context, store=case.store, workflow=case.factory(), checkpoint_storage=case.storage,
    )
    assert result.approval_evidence.approval_id == case.request.approval_id
    assert result.approval_evidence.decision.value == decision
    assert result.approval_evidence.channel == "local-test"
    assert result.safe_communication_context.alert_id == case.request.alert_id
    assert case.store.get_consumption_record(case.request.approval_id) == ("completed", decision == "approve")
    assert case.agents.calls.count("azure_operations") == (1 if decision == "approve" else 0)
    calls_before_replay = list(case.agents.calls)
    with pytest.raises(ApprovalAlreadyConsumedError):
        await processor.process_authorized_incident_approval(
            invocation=context, store=case.store, workflow=case.factory(), checkpoint_storage=case.storage,
        )
    assert case.agents.calls == calls_before_replay


@pytest.mark.asyncio
async def test_other_conversation_cannot_claim_native_approval(tmp_path):
    case = await prepare_native_case(tmp_path)
    with pytest.raises(ApprovalResumeMismatchError):
        await processor.process_authorized_incident_approval(
            invocation=decision_context(case.request, conversation="another-conversation"),
            store=case.store, workflow=case.factory(), checkpoint_storage=case.storage,
        )
    assert case.store.get_consumption_record(case.request.approval_id) == ("pending", None)
    assert "azure_operations" not in case.agents.calls


@pytest.mark.asyncio
async def test_missing_safe_checkpoint_context_blocks_claim(tmp_path):
    case = await prepare_native_case(tmp_path)
    del case.checkpoint.state[SAFE_COMMUNICATION_CONTEXT_STATE_KEY]
    await case.storage.save(case.checkpoint)
    with pytest.raises(CommunicationCheckpointRecoveryError):
        await processor.process_authorized_incident_approval(
            invocation=decision_context(case.request), store=case.store,
            workflow=case.factory(), checkpoint_storage=case.storage,
        )
    assert case.store.get_consumption_record(case.request.approval_id) == ("pending", None)
    assert "azure_operations" not in case.agents.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["no-output", "two-outputs", "new-request", "wrong-workflow",
                                      "wrong-approval", "response-error", "evidence-error"])
async def test_failure_after_claim_never_reopens_consumption(tmp_path, monkeypatch, failure):
    request = create_restored_request()
    store = SqlitePendingApprovalStore(tmp_path / "approval.db")
    store.register(PendingApprovalCorrelation(approval_id=request.approval_id, workflow_id=request.workflow_id,
                                             request_id="native-request", checkpoint_id="checkpoint"))
    response_calls = []
    class Workflow:
        name = "synthetic-incident"
        async def run(self, **kwargs):
            if "responses" not in kwargs:
                yield SimpleNamespace(type="request_info", request_id="native-request", data=request)
                return
            response_calls.append(kwargs["responses"])
            if failure == "response-error":
                raise RuntimeError("synthetic response failure")
            if failure == "new-request":
                yield SimpleNamespace(type="request_info", data=request)
                return
            result = SimpleNamespace(workflow_id=request.workflow_id, approval_id=request.approval_id)
            if failure == "wrong-workflow":
                result.workflow_id = "different"
            if failure == "wrong-approval":
                result.approval_id = "different"
            for _ in range(0 if failure == "no-output" else 2 if failure == "two-outputs" else 1):
                yield SimpleNamespace(type="output", data=result)
    async def safe_context(**kwargs):
        return object()
    monkeypatch.setattr(processor, "recover_safe_communication_context_from_checkpoint", safe_context)
    if failure == "evidence-error":
        def fail_evidence(**kwargs):
            raise evidence.ApprovalEvidenceError("synthetic evidence failure")
        monkeypatch.setattr(processor, "build_approval_evidence_from_request", fail_evidence)
    context = decision_context(request)
    with pytest.raises((processor.IncidentApprovalProcessingError, evidence.ApprovalEvidenceError, RuntimeError)):
        await processor.process_authorized_incident_approval(
            invocation=context, store=store, workflow=Workflow(), checkpoint_storage=object(),
        )
    assert store.get_consumption_record(request.approval_id) == ("claimed", True)
    with pytest.raises(ApprovalAlreadyConsumedError):
        await processor.process_authorized_incident_approval(
            invocation=context, store=store, workflow=Workflow(), checkpoint_storage=object(),
        )
    assert response_calls == [{"native-request": True}]


def test_native_core_processor_runs_in_fresh_process_without_teams(tmp_path):
    code = r'''
import importlib.abc, sys
class NoChannel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "src.channels" or fullname.startswith(("src.channels.", "microsoft_teams")):
            raise AssertionError("Core imported a channel: " + fullname)
sys.meta_path.insert(0, NoChannel())
import asyncio
from pathlib import Path
from src.runtime.incident_approval_processor import process_authorized_incident_approval
from src.runtime.procedure.approval_processor import process_authorized_approval
from tests.runtime._neutral_incident_case import prepare_native_case, decision_context
async def main():
    case = await prepare_native_case(Path(sys.argv[1]))
    result = await process_authorized_incident_approval(
        invocation=decision_context(case.request, "reject"), store=case.store,
        workflow=case.factory(), checkpoint_storage=case.storage,
    )
    assert result.approval_evidence.channel == "local-test"
    assert result.approval_evidence.decision.value == "reject"
    assert case.store.get_consumption_record(case.request.approval_id) == ("completed", False)
    assert "azure_operations" not in case.agents.calls
asyncio.run(main())
'''
    result = subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
