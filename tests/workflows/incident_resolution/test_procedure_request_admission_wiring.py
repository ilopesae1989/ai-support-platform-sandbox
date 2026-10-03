from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import src.workflows.incident_resolution.executors.routing as routing_module
import src.workflows.incident_resolution.workflow as workflow_module

from src.workflows.incident_resolution.alert_models import NormalizedAlert
from src.workflows.incident_resolution.executors.routing import ProcedureRequestExecutor
from src.workflows.incident_resolution.procedure_admission import (
    ProcedureAdmissionPolicy,
    ProcedureNotAdmittedError,
)
from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)


class FakeWorkflowContext:
    def __init__(self) -> None:
        self.messages = []
        self.outputs = []
        self.state = {}

    def set_state(self, key, value) -> None:
        self.state[key] = value

    def get_state(self, key, default=None):
        return self.state.get(key, default)

    async def send_message(self, message) -> None:
        self.messages.append(message)

    async def yield_output(self, output) -> None:
        self.outputs.append(output)


def build_test_policy() -> ProcedureAdmissionPolicy:
    return ProcedureAdmissionPolicy(
        catalog=ProcedureCatalog(
            definitions=(
                ProcedureDefinition(
                    procedure_id="PROC-001",
                    procedure_version="v1",
                    procedure_name="Test Procedure",
                    lifecycle="published",
                    step_ids=("1",),
                ),
            )
        ),
        legacy_compatibility=(),
    )


def build_context(
    *,
    procedure_id="PROC-001",
    procedure_version="v1",
    procedure_name="Test Procedure",
):
    alert = NormalizedAlert(
        alert_id="ALT-TEST-001",
        source="scom",
        source_event_id="SCOM-TEST-001",
        name="Test Alert",
        description="Alerta utilizada para pruebas de admission.",
        source_severity="Critical",
        timestamp="2026-08-08T12:00:00Z",
        affected_resource="SERVER01",
        resource_type="TestResource",
        service="Test Service",
        correlation_id="corr-test-001",
    )

    procedure = SimpleNamespace(
        id=procedure_id,
        version=procedure_version,
        name=procedure_name,
    )

    triage = SimpleNamespace(
        procedure_found=True,
        procedure_match="exact",
        execution_eligible=True,
        recommended_next_step="procedure_execution",
        procedure=procedure,
        affected_resource="SERVER01",
    )

    return SimpleNamespace(
        alert=alert,
        triage=triage,
    )


def test_executor_constructor_requires_admission_policy():
    signature = inspect.signature(ProcedureRequestExecutor)
    assert tuple(signature.parameters) == ("admission_policy",)
    parameter = signature.parameters["admission_policy"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_executor_cannot_be_constructed_without_admission_policy():
    with pytest.raises(TypeError):
        ProcedureRequestExecutor()


def test_executor_rejects_none_policy_explicitly():
    with pytest.raises(
        TypeError,
        match="ProcedureAdmissionPolicy",
    ):
        ProcedureRequestExecutor(
            admission_policy=None,
        )


@pytest.mark.asyncio
async def test_executor_admits_exact_identity_before_creating_request():
    executor = ProcedureRequestExecutor(
        admission_policy=build_test_policy(),
    )
    ctx = FakeWorkflowContext()

    await executor.prepare_procedure_request(
        build_context(),
        ctx,
    )

    assert len(ctx.messages) == 1
    request = ctx.messages[0].request
    assert request.procedure_id == "PROC-001"
    assert request.procedure_version == "v1"
    assert request.procedure_name == "Test Procedure"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("procedure_id", "procedure_version", "procedure_name"),
    (
        ("PROC-999", "v1", "Test Procedure"),
        ("PROC-001", "v9", "Test Procedure"),
        ("PROC-001", "v1", "test procedure"),
    ),
)
async def test_executor_rejects_identity_drift_before_side_effects(
    monkeypatch,
    procedure_id,
    procedure_version,
    procedure_name,
):
    executor = ProcedureRequestExecutor(
        admission_policy=build_test_policy(),
    )
    ctx = FakeWorkflowContext()

    def forbidden_workflow_id():
        pytest.fail("create_workflow_id_called_before_admission")

    def forbidden_operational_context(_alert):
        pytest.fail("build_operational_context_called_before_admission")

    monkeypatch.setattr(
        routing_module,
        "create_workflow_id",
        forbidden_workflow_id,
    )
    monkeypatch.setattr(
        routing_module,
        "build_operational_context",
        forbidden_operational_context,
    )

    with pytest.raises(ProcedureNotAdmittedError):
        await executor.prepare_procedure_request(
            build_context(
                procedure_id=procedure_id,
                procedure_version=procedure_version,
                procedure_name=procedure_name,
            ),
            ctx,
        )

    assert ctx.messages == []
    assert ctx.outputs == []
    assert ctx.state == {}


def test_workflow_builder_exposes_optional_admission_policy_injection():
    signature = inspect.signature(
        workflow_module.build_incident_resolution_workflow
    )
    assert "procedure_admission_policy" in signature.parameters
    parameter = signature.parameters["procedure_admission_policy"]
    assert parameter.default is None


def test_workflow_builder_constructs_default_policy_and_injects_executor():
    source = inspect.getsource(
        workflow_module.build_incident_resolution_workflow
    )

    assert "build_default_procedure_admission_policy" in source
    assert "procedure_admission_policy" in source
    assert "ProcedureRequestExecutor(" in source
    assert "admission_policy=" in source


def test_routing_module_has_no_none_policy_bypass():
    source = inspect.getsource(ProcedureRequestExecutor)

    assert "admission_policy" in source
    assert ".admit(" in source
    assert "if admission_policy is None" not in source
    assert "admission_policy or" not in source
