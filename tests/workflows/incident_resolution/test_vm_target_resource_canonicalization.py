from types import SimpleNamespace

import pytest

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)


def resolve_target(
    context,
):
    return (
        ProcedureRuntimeExecutor()
        ._resolve_authoritative_target_resource(
            context
        )
    )


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

CANONICAL_RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)


def create_context(
    *,
    target_resource=VM_NAME,
    required_parameters=None,
    affected_resource=VM_NAME,
    subscription_id=SUBSCRIPTION_ID,
    resource_group=RESOURCE_GROUP,
    vm_name=VM_NAME,
):
    if required_parameters is None:
        required_parameters = [
            "subscription_id",
            "resource_group",
            "vm_name",
        ]

    step = SimpleNamespace(
        operation_domain="azure",

        target_resource=(
            target_resource
        ),

        required_parameters=(
            required_parameters
        ),
    )

    result = SimpleNamespace(
        step=step
    )

    operational = SimpleNamespace(
        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        affected_resource=(
            affected_resource
        ),

        subscription_id=(
            subscription_id
        ),

        resource_group=(
            resource_group
        ),

        vm_name=(
            vm_name
        ),
    )

    return SimpleNamespace(
        result=result,
        operational_context=operational,
    )


def test_vm_name_becomes_canonical_arm_resource_id():
    context = create_context(
        target_resource=VM_NAME
    )

    result = (
        resolve_target(
            context
        )
    )

    assert (
        result
        == CANONICAL_RESOURCE_ID
    )


def test_exact_arm_resource_id_is_preserved_canonically():
    context = create_context(
        target_resource=(
            CANONICAL_RESOURCE_ID
        )
    )

    result = (
        resolve_target(
            context
        )
    )

    assert (
        result
        == CANONICAL_RESOURCE_ID
    )


def test_rejects_different_vm_target():
    context = create_context(
        target_resource=(
            "vm-attacker-01"
        )
    )

    with pytest.raises(
        ValueError,
        match="target_resource",
    ):
        resolve_target(
            context
        )


def test_rejects_missing_target_resource():
    context = create_context(
        target_resource=None
    )

    with pytest.raises(
        ValueError,
        match="target_resource",
    ):
        resolve_target(
            context
        )


def test_rejects_incomplete_vm_parameter_contract():
    context = create_context(
        required_parameters=[
            "resource_group",
            "vm_name",
        ]
    )

    with pytest.raises(
        ValueError,
        match="required_parameters",
    ):
        resolve_target(
            context
        )


def test_rejects_reordered_vm_parameter_contract():
    context = create_context(
        required_parameters=[
            "vm_name",
            "resource_group",
            "subscription_id",
        ]
    )

    with pytest.raises(
        ValueError,
        match="required_parameters",
    ):
        resolve_target(
            context
        )


def test_rejects_affected_resource_different_from_vm_name():
    context = create_context(
        affected_resource=(
            "vm-attacker-01"
        )
    )

    with pytest.raises(
        ValueError,
        match="affected_resource",
    ):
        resolve_target(
            context
        )


@pytest.mark.parametrize(
    (
        "parameter_name",
        "parameter_value",
    ),
    [
        (
            "subscription_id",
            None,
        ),
        (
            "resource_group",
            None,
        ),
        (
            "vm_name",
            None,
        ),
    ],
)
def test_rejects_missing_authoritative_vm_identity(
    parameter_name,
    parameter_value,
):
    kwargs = {
        parameter_name:
            parameter_value
    }

    context = create_context(
        **kwargs
    )

    with pytest.raises(
        ValueError,
    ):
        resolve_target(
            context
        )