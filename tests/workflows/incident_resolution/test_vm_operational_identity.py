from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.operational_context import (
    build_operational_context,
)

from src.workflows.incident_resolution.parameter_resolution import (
    resolve_required_parameters,
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


def create_vm_alert(
    *,
    vm_name: str | None = VM_NAME,
):
    return NormalizedAlert(
        alert_id="ALT-VM-DEALLOCATED-001",

        source="azure_monitor",

        source_event_id=(
            "AZMON-VM-001"
        ),

        name=(
            "Virtual machine is deallocated"
        ),

        description=(
            "La máquina virtual se encuentra "
            "detenida."
        ),

        source_severity="Sev2",

        affected_resource=VM_NAME,

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        service="Azure Virtual Machines",

        environment="sandbox",

        subscription_id=(
            SUBSCRIPTION_ID
        ),

        resource_group=(
            RESOURCE_GROUP
        ),

        vm_name=vm_name,

        correlation_id=(
            "corr-vm-deallocated-001"
        ),

        raw_attributes={
            #
            # Un valor arbitrario de la fuente NO puede
            # sustituir el campo tipado.
            #
            "vm_name":
                "vm-attacker-01",
        },
    )


def test_operational_context_preserves_exact_vm_identity():
    alert = create_vm_alert()

    context = (
        build_operational_context(
            alert
        )
    )

    assert (
        context.subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        context.resource_group
        == RESOURCE_GROUP
    )

    assert (
        context.vm_name
        == VM_NAME
    )

    assert (
        context.resource_type
        == "Microsoft.Compute/virtualMachines"
    )


def test_vm_parameters_resolve_only_from_typed_alert_fields():
    alert = create_vm_alert()

    context = (
        build_operational_context(
            alert
        )
    )

    result = (
        resolve_required_parameters(
            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],

            context=context,
        )
    )

    assert result.complete is True

    assert (
        result.missing_parameters
        == []
    )

    assert [
        parameter.name
        for parameter
        in result.resolved_parameters
    ] == [
        "subscription_id",
        "resource_group",
        "vm_name",
    ]

    assert [
        parameter.value
        for parameter
        in result.resolved_parameters
    ] == [
        SUBSCRIPTION_ID,
        RESOURCE_GROUP,
        VM_NAME,
    ]

    assert [
        parameter.source
        for parameter
        in result.resolved_parameters
    ] == [
        "normalized_alert.subscription_id",
        "normalized_alert.resource_group",
        "normalized_alert.vm_name",
    ]


def test_raw_attributes_cannot_override_vm_name():
    alert = create_vm_alert()

    context = (
        build_operational_context(
            alert
        )
    )

    result = (
        resolve_required_parameters(
            required_parameters=[
                "vm_name",
            ],

            context=context,
        )
    )

    assert result.complete is True

    assert (
        result.resolved_parameters[0].value
        == VM_NAME
    )

    assert (
        result.resolved_parameters[0].value
        != "vm-attacker-01"
    )


def test_missing_typed_vm_name_fails_closed():
    alert = create_vm_alert(
        vm_name=None
    )

    context = (
        build_operational_context(
            alert
        )
    )

    result = (
        resolve_required_parameters(
            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],

            context=context,
        )
    )

    assert result.complete is False

    assert (
        result.missing_parameters
        == [
            "vm_name",
        ]
    )


def test_vm_name_alias_is_not_supported():
    alert = create_vm_alert()

    context = (
        build_operational_context(
            alert
        )
    )

    result = (
        resolve_required_parameters(
            required_parameters=[
                "virtual_machine",
            ],

            context=context,
        )
    )

    assert result.complete is False

    assert (
        result.missing_parameters
        == [
            "virtual_machine",
        ]
    )