"""Channel-independent composition of the existing incident workflow.

These dependencies come from a trusted host. They are not incident input,
approval evidence or authority reconstructed from a checkpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from collections.abc import Mapping

from agent_framework import CheckpointStorage, Workflow
from src.runtime.procedure.approval_store import PendingApprovalStore

from src.config.procedure_configuration import ProcedureConfiguration
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingRegistry,
)
from src.workflows.incident_resolution.vm_start_foundry_binding import (
    GovernedVmStartRoute, VmStartFoundryBinding,
)
from src.workflows.incident_resolution.workflow import build_incident_resolution_workflow
from src.workflows.incident_resolution.azure_vm_instance_view import AzureVmPowerStateReader
from src.workflows.incident_resolution.operation_dispatch_ledger import OperationDispatchLedger
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import WaitRecheckConsumptionLedger


@dataclass(frozen=True, kw_only=True)
class IncidentWorkflowOptions:
    """Validate selection before a channel creates its provider dependencies."""

    agents: object | None = None
    capability_foundry_agent_binding_registry: CapabilityFoundryAgentBindingRegistry | None = None
    vm_start_binding: VmStartFoundryBinding | None = None
    vm_start_route: GovernedVmStartRoute | None = None
    procedure_configuration: ProcedureConfiguration | None = None
    attestation_publisher: object | None = None

    def __post_init__(self) -> None:
        expected_types = (
            ("capability_foundry_agent_binding_registry", CapabilityFoundryAgentBindingRegistry),
            ("vm_start_binding", VmStartFoundryBinding),
            ("vm_start_route", GovernedVmStartRoute),
            ("procedure_configuration", ProcedureConfiguration),
        )
        for name, expected in expected_types:
            value = getattr(self, name)
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}.")
        if self.vm_start_binding is not None and self.vm_start_route is not None:
            raise ValueError("Specify vm_start_binding or vm_start_route, never both.")
        if self.attestation_publisher is not None:
            from src.attestation.governor_outbox import GovernorAttestationPublisher
            if type(self.attestation_publisher) is not GovernorAttestationPublisher:
                raise TypeError("Explicit governor attestation publisher required")


@dataclass(frozen=True, kw_only=True)
class IncidentWorkflowFactory:
    """New graph per call, same injected agents and consumption authorities."""

    _arguments: Mapping[str, object] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_arguments", MappingProxyType(dict(self._arguments)))

    def __call__(self) -> Workflow:
        return build_incident_resolution_workflow(**self._arguments)


def build_incident_workflow_factory(
    *,
    approval_store: PendingApprovalStore,
    checkpoint_storage: CheckpointStorage,
    operation_dispatch_ledger: OperationDispatchLedger,
    wait_recheck_consumption_ledger: WaitRecheckConsumptionLedger,
    azure_vm_power_state_reader: AzureVmPowerStateReader | None = None,
    options: IncidentWorkflowOptions,
) -> IncidentWorkflowFactory:
    """Bind existing stores without opening SQL, invoking agents or starting a host.

    Store implementations remain host responsibilities. Requiring explicit
    objects prevents the composed path from selecting in-memory ledgers by
    omission; it does not certify their durability or a remote deployment.
    """
    if not isinstance(options, IncidentWorkflowOptions):
        raise TypeError("options must be IncidentWorkflowOptions.")
    for name, dependency in (
        ("approval_store", approval_store),
        ("checkpoint_storage", checkpoint_storage),
        ("operation_dispatch_ledger", operation_dispatch_ledger),
        ("wait_recheck_consumption_ledger", wait_recheck_consumption_ledger),
    ):
        if dependency is None:
            raise TypeError(f"{name} must be explicitly injected.")

    arguments = {
        "operation_dispatch_ledger": operation_dispatch_ledger,
        "wait_recheck_consumption_ledger": wait_recheck_consumption_ledger,
        "azure_vm_power_state_reader": azure_vm_power_state_reader,
    }
    for name in ("agents", "capability_foundry_agent_binding_registry",
                 "vm_start_route", "attestation_publisher"):
        value = getattr(options, name)
        if value is not None:
            arguments[name] = value
    if options.procedure_configuration is not None:
        arguments.update(options.procedure_configuration.workflow_options())
    if options.vm_start_binding is not None:
        from src.workflows.incident_resolution.vm_start_approval_binding import (
            CheckpointApprovedVmStartBindingReader,
        )
        arguments["vm_start_route"] = GovernedVmStartRoute(
            binding=options.vm_start_binding,
            approval_binding_reader=CheckpointApprovedVmStartBindingReader(
                store=approval_store, checkpoint_storage=checkpoint_storage,
            ),
        )
    return IncidentWorkflowFactory(_arguments=arguments)
