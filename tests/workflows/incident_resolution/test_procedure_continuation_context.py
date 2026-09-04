import importlib
import json

import pytest
from pydantic import ValidationError


MODULE_NAME = (
    "src.workflows.incident_resolution."
    "continuation_context"
)

EXPECTED_FIELDS = [
    "request_affected_resource",
    "incident_description",
    "operational_affected_resource",
    "resource_type",
    "service",
    "environment",
    "incident_origin",
    "subscription_id",
    "resource_group",
    "vm_name",
    "tenant_id",
]


def load_contract_module():
    try:
        return importlib.import_module(
            MODULE_NAME
        )
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Procedure continuation context "
            f"contract is missing: {exc}"
        )


def get_context_class():
    module = load_contract_module()

    model = getattr(
        module,
        "ProcedureContinuationContext",
        None,
    )

    assert model is not None

    return model


def make_context():
    model = get_context_class()

    return model(
        request_affected_resource=(
            "vm-icenter-sbx-demo-01"
        ),
        incident_description=(
            "La VM requiere tratamiento "
            "operacional controlado."
        ),
        operational_affected_resource=(
            "vm-icenter-sbx-demo-01"
        ),
        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),
        service=(
            "Azure Virtual Machines"
        ),
        environment="sandbox",
        incident_origin="observed",
        subscription_id=(
            "557fdabc-f3b6-4c24-"
            "a9ae-e9e89b5ad172"
        ),
        resource_group=(
            "rg-icenter-sandbox-vm-demo"
        ),
        vm_name=(
            "vm-icenter-sbx-demo-01"
        ),
        tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),
    )


class FakeWorkflowContext:
    def __init__(self):
        self.state = {}

    def set_state(
        self,
        key,
        value,
    ):
        self.state[key] = value

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.state.get(
            key,
            default,
        )


def test_continuation_context_has_exact_minimal_fields():
    model = get_context_class()

    assert (
        list(model.model_fields)
        == EXPECTED_FIELDS
    )

    forbidden = {
        "workflow_id",
        "alert_id",
        "correlation_id",
        "procedure_id",
        "procedure_name",
        "procedure_version",
        "requested_step",
        "current_step",
        "step",
        "approval_id",
        "operation_result",
        "verification_result",
    }

    assert (
        forbidden.intersection(
            model.model_fields
        )
        == set()
    )


def test_continuation_context_forbids_duplicate_authority():
    model = get_context_class()

    payload = (
        make_context()
        .model_dump(
            mode="json"
        )
    )

    payload["alert_id"] = "ALT-ATTACKER"

    with pytest.raises(
        ValidationError
    ):
        model.model_validate(
            payload
        )

    payload = (
        make_context()
        .model_dump(
            mode="json"
        )
    )

    payload["requested_step"] = 999

    with pytest.raises(
        ValidationError
    ):
        model.model_validate(
            payload
        )


def test_continuation_context_is_json_native_and_roundtrippable():
    model = get_context_class()

    context = make_context()

    payload = context.model_dump(
        mode="json"
    )

    json.dumps(
        payload
    )

    restored = model.model_validate(
        payload
    )

    assert (
        restored
        == context
    )


def test_store_uses_exact_shared_state_key_and_json_payload():
    module = load_contract_module()

    key = getattr(
        module,
        "PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY",
        None,
    )

    store = getattr(
        module,
        "store_procedure_continuation_context",
        None,
    )

    assert (
        key
        == "procedure_continuation_context"
    )

    assert callable(
        store
    )

    context = make_context()
    ctx = FakeWorkflowContext()

    store(
        ctx,
        context,
    )

    assert (
        ctx.state
        == {
            "procedure_continuation_context":
                context.model_dump(
                    mode="json"
                )
        }
    )


def test_load_missing_context_preserves_old_checkpoint_compatibility():
    module = load_contract_module()

    load = getattr(
        module,
        "load_procedure_continuation_context",
        None,
    )

    assert callable(
        load
    )

    ctx = FakeWorkflowContext()

    assert (
        load(ctx)
        is None
    )


def test_load_corrupt_context_fails_closed():
    module = load_contract_module()

    load = getattr(
        module,
        "load_procedure_continuation_context",
        None,
    )

    assert callable(
        load
    )

    context = make_context()

    payload = context.model_dump(
        mode="json"
    )

    payload["incident_origin"] = (
        "attacker_controlled"
    )

    ctx = FakeWorkflowContext()

    ctx.state[
        "procedure_continuation_context"
    ] = payload

    with pytest.raises(
        ValidationError
    ):
        load(
            ctx
        )


def test_load_valid_context_rehydrates_exact_model():
    module = load_contract_module()

    load = getattr(
        module,
        "load_procedure_continuation_context",
        None,
    )

    assert callable(
        load
    )

    original = make_context()

    ctx = FakeWorkflowContext()

    ctx.state[
        "procedure_continuation_context"
    ] = original.model_dump(
        mode="json"
    )

    restored = load(
        ctx
    )

    assert (
        restored
        == original
    )

    assert (
        restored
        is not original
    )
