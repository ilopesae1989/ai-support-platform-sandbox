from __future__ import annotations

from importlib import import_module

import pytest
from pydantic import ValidationError

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)

from tests.communication.test_communication_projection import (
    _context,
)


def _module():
    try:
        return import_module(
            "src.communication.context"
        )
    except ModuleNotFoundError as exc:
        if exc.name != "src.communication.context":
            raise

        pytest.fail(
            "SafeCommunicationContext "
            "is not implemented.",
            pytrace=False,
        )


def test_safe_context_has_exact_presentation_fields():
    module = _module()

    fields = set(
        module.SafeCommunicationContext.model_fields
    )

    assert fields == {
        "alert_id",
        "technical_domain",
        "corporate_criticality",
        "affected_resource",
        "technical_summary",
        "procedure_id",
        "procedure_name",
    }


def test_safe_context_is_frozen_and_forbids_extras():
    module = _module()

    context = module.SafeCommunicationContext(
        alert_id="ALERT-SYNTHETIC-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-synthetic",
        technical_summary="Synthetic incident.",
        procedure_id="PROC-SYNTHETIC-001",
        procedure_name="Synthetic procedure",
    )

    with pytest.raises(
        ValidationError
    ):
        context.alert_id = "changed"

    with pytest.raises(
        ValidationError
    ):
        module.SafeCommunicationContext(
            alert_id="ALERT-SYNTHETIC-001",
            technical_domain="azure",
            corporate_criticality="high",
            affected_resource="vm-synthetic",
            technical_summary="Synthetic incident.",
            procedure_id="PROC-SYNTHETIC-001",
            procedure_name="Synthetic procedure",
            approval_id="approval-forbidden",
        )


def test_safe_context_requires_procedure_pair_or_neither():
    module = _module()

    with pytest.raises(
        ValidationError
    ):
        module.SafeCommunicationContext(
            alert_id="ALERT-SYNTHETIC-001",
            technical_domain="azure",
            corporate_criticality="high",
            affected_resource="vm-synthetic",
            technical_summary="Synthetic incident.",
            procedure_id="PROC-SYNTHETIC-001",
            procedure_name=None,
        )

    context = module.SafeCommunicationContext(
        alert_id="ALERT-SYNTHETIC-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource=None,
        technical_summary="Synthetic incident.",
        procedure_id=None,
        procedure_name=None,
    )

    assert context.procedure_id is None
    assert context.procedure_name is None


def test_builder_requires_exact_triaged_context():
    module = _module()

    with pytest.raises(TypeError):
        module.build_safe_communication_context(
            object()
        )


def test_builder_copies_only_governed_triage_fields():
    module = _module()

    source = _context()

    result = (
        module.build_safe_communication_context(
            source
        )
    )

    assert isinstance(
        result,
        module.SafeCommunicationContext,
    )

    assert result.alert_id == (
        source.alert.alert_id
    )

    assert result.technical_domain == (
        source.triage.technical_domain
    )

    assert result.corporate_criticality == (
        source.triage.corporate_criticality
    )

    assert result.affected_resource == (
        source.triage.affected_resource
    )

    assert result.technical_summary == (
        source.triage.technical_summary
    )

    assert result.procedure_id == (
        source.triage.procedure.id
    )

    assert result.procedure_name == (
        source.triage.procedure.name
    )


def test_builder_does_not_fallback_to_alert_resource():
    module = _module()

    source = _context()

    triage = source.triage.model_copy(
        update={
            "affected_resource": None,
        }
    )

    modified = TriagedAlertContext(
        alert=source.alert,
        classification=source.classification,
        knowledge=source.knowledge,
        triage=triage,
    )

    result = (
        module.build_safe_communication_context(
            modified
        )
    )

    assert result.affected_resource is None


def test_builder_supports_no_procedure():
    module = _module()

    source = _context()

    triage = source.triage.model_copy(
        update={
            "procedure_found": False,
            "procedure_match": "none",
            "execution_eligible": False,
            "knowledge_coverage": "none",
            "recommended_next_step": "manual_analysis",
            "procedure": None,
        }
    )

    modified = TriagedAlertContext(
        alert=source.alert,
        classification=source.classification,
        knowledge=source.knowledge,
        triage=triage,
    )

    result = (
        module.build_safe_communication_context(
            modified
        )
    )

    assert result.procedure_id is None
    assert result.procedure_name is None


def test_serialized_snapshot_is_json_native_and_safe():
    module = _module()

    snapshot = (
        module.build_safe_communication_context(
            _context()
        )
    )

    payload = snapshot.model_dump(
        mode="json"
    )

    assert payload == {
        "alert_id": snapshot.alert_id,
        "technical_domain": (
            snapshot.technical_domain
        ),
        "corporate_criticality": (
            snapshot.corporate_criticality
        ),
        "affected_resource": (
            snapshot.affected_resource
        ),
        "technical_summary": (
            snapshot.technical_summary
        ),
        "procedure_id": (
            snapshot.procedure_id
        ),
        "procedure_name": (
            snapshot.procedure_name
        ),
    }

    forbidden = {
        "workflow_id",
        "correlation_id",
        "approval_id",
        "conversation_id",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "capability_id",
        "operation_action",
        "target_resource",
        "resolved_parameters",
        "operation_result",
        "verification_result",
        "retry_count",
        "recheck_count",
    }

    assert forbidden.isdisjoint(
        payload
    )
