from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from .incident_launcher import (
    start_teams_incident_from_normalized_alert,
)


DEMO_SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

DEMO_RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

DEMO_VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

DEMO_RESOURCE_TYPE = (
    "Microsoft.Compute/virtualMachines"
)

DEMO_RESOURCE_ID = (
    "/subscriptions/"
    f"{DEMO_SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{DEMO_RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{DEMO_VM_NAME}"
)

SyntheticVmObservedPowerState = Literal[
    "PowerState/stopped",
    "PowerState/deallocated",
]

_ALLOWED_POWER_STATES = (
    "PowerState/stopped",
    "PowerState/deallocated",
)


class SyntheticVmStartHarnessError(
    ValueError
):
    """
    Error fail-closed del harness sintético
    gobernado de VM START.

    El harness no concede autoridad operacional.
    """

    pass


def _require_exact_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value
        != value.strip()
    ):
        raise SyntheticVmStartHarnessError(
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


def _require_observed_power_state(
    value: object,
) -> SyntheticVmObservedPowerState:
    if (
        not isinstance(
            value,
            str,
        )
        or value
        not in _ALLOWED_POWER_STATES
    ):
        raise SyntheticVmStartHarnessError(
            "observed_power_state debe ser "
            "exactamente PowerState/stopped "
            "o PowerState/deallocated."
        )

    return value


def build_exact_synthetic_vm_start_alert(
    *,
    alert_id: str,
    source_event_id: str,
    correlation_id: str,
    observed_power_state: (
        SyntheticVmObservedPowerState
    ),
    timestamp: datetime | None = None,
) -> NormalizedAlert:
    """
    Construye exclusivamente el hecho sintético
    que inicia la demo gobernada de VM START.

    El target operacional está fijado a la VM
    sandbox certificada.

    Este input NO contiene:

    - procedure_id;
    - capability_id;
    - operation_action;
    - approval;
    - identidad del operador;
    - destino Teams;
    - autoridad derivada de raw_attributes.

    El procedimiento debe seguir siendo recuperado
    por el pipeline cognitivo y validado después por
    las capas deterministas Python.
    """

    alert_id = _require_exact_string(
        name="alert_id",
        value=alert_id,
    )

    source_event_id = _require_exact_string(
        name="source_event_id",
        value=source_event_id,
    )

    correlation_id = _require_exact_string(
        name="correlation_id",
        value=correlation_id,
    )

    observed_power_state = (
        _require_observed_power_state(
            observed_power_state
        )
    )

    if (
        observed_power_state
        == "PowerState/stopped"
    ):
        state_description = (
            "PowerState/stopped "
            "(Stopped Allocated)"
        )
    else:
        state_description = (
            "PowerState/deallocated "
            "(Deallocated)"
        )

    return NormalizedAlert(
        alert_id=alert_id,

        source="azure_monitor",

        incident_origin=(
            "synthetic_demo"
        ),

        source_event_id=(
            source_event_id
        ),

        name=(
            "Azure VM unexpected "
            "power state"
        ),

        description=(
            "Incidente sintético gobernado de "
            "sandbox. La máquina virtual "
            f"{DEMO_VM_NAME} se encuentra en "
            f"{state_description}. "
            "La máquina virtual debería estar "
            "en ejecución y no existe "
            "mantenimiento ni parada planificada "
            "conocida."
        ),

        source_severity="Critical",

        timestamp=timestamp,

        affected_resource=(
            DEMO_RESOURCE_ID
        ),

        resource_type=(
            DEMO_RESOURCE_TYPE
        ),

        service=(
            "Azure Virtual Machines"
        ),

        environment="sandbox",

        subscription_id=(
            DEMO_SUBSCRIPTION_ID
        ),

        resource_group=(
            DEMO_RESOURCE_GROUP
        ),

        vm_name=(
            DEMO_VM_NAME
        ),

        tenant_id=None,

        correlation_id=(
            correlation_id
        ),

        raw_attributes={},
    )


async def run_exact_synthetic_vm_start_until_teams_approval(
    *,
    bootstrap: Any,
    tenant_id: str,
    conversation_id: str,
    alert_id: str,
    source_event_id: str,
    correlation_id: str,
    observed_power_state: (
        SyntheticVmObservedPowerState
    ),
    timestamp: datetime | None = None,
):
    """
    Entrega el incidente sintético exacto al
    launcher Teams ya existente.

    No crea otro workflow.
    No crea otro checkpoint store.
    No crea otro approval store.
    No crea otro outbound adapter.
    No arranca el servidor Teams.

    El destino Teams es un input separado del
    NormalizedAlert y nunca se deriva del mismo.
    """

    tenant_id = _require_exact_string(
        name="tenant_id",
        value=tenant_id,
    )

    conversation_id = _require_exact_string(
        name="conversation_id",
        value=conversation_id,
    )

    dependencies = getattr(
        bootstrap,
        "dependencies",
        None,
    )

    workflow_factory = getattr(
        dependencies,
        "workflow_factory",
        None,
    )

    if not callable(
        workflow_factory
    ):
        raise SyntheticVmStartHarnessError(
            "bootstrap.dependencies."
            "workflow_factory debe ser callable."
        )

    checkpoint_storage = getattr(
        bootstrap,
        "checkpoint_storage",
        None,
    )

    if checkpoint_storage is None:
        raise SyntheticVmStartHarnessError(
            "bootstrap no contiene "
            "checkpoint_storage."
        )

    store = getattr(
        bootstrap,
        "store",
        None,
    )

    if store is None:
        raise SyntheticVmStartHarnessError(
            "bootstrap no contiene store."
        )

    outbound = getattr(
        bootstrap,
        "outbound",
        None,
    )

    if outbound is None:
        raise SyntheticVmStartHarnessError(
            "bootstrap no contiene outbound."
        )

    alert = (
        build_exact_synthetic_vm_start_alert(
            alert_id=alert_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            observed_power_state=(
                observed_power_state
            ),
            timestamp=timestamp,
        )
    )

    return await (
        start_teams_incident_from_normalized_alert(
            alert=alert,
            workflow_factory=(
                workflow_factory
            ),
            checkpoint_storage=(
                checkpoint_storage
            ),
            store=store,
            outbound=outbound,
            tenant_id=tenant_id,
            conversation_id=(
                conversation_id
            ),
        )
    )
