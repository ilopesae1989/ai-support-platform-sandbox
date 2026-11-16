from __future__ import annotations

from .vm_start_foundry_binding import GovernedVmStartRoute

from dataclasses import dataclass

from src.agents.foundry_agents import FoundryAgents

from .azure_vm_instance_view import AzureVmPowerStateReader
from .capability_foundry_agent_binding import CapabilityFoundryAgentBindingRegistry
from .azure_read_tool_authority import AzureReadToolAuthorityRegistry
from .domain_execution_binding import DomainExecutionBinding
from .domain_execution_path import DomainExecutionPath
from .executors.azure_operations import AzureOperationsExecutor
from .executors.azure_pre_call import AzurePreCallSecurityExecutor
from .executors.azure_vm_post_operation_observation import (
    AzureVmPostOperationObservationExecutor,
)
from .executors.operation_lifecycle import OperationStartExecutor
from .operation_dispatch_ledger import OperationDispatchLedger
from .wait_recheck_consumption_ledger import WaitRecheckConsumptionLedger


@dataclass(frozen=True)
class AzureDomainComposition:
    """Referencias de composicion Azure; no es un executor ni un workflow.

    Congela las referencias, no el estado interno de los componentes.
    No concede authority ni demuestra que el grafo este conectado.
    """

    pre_call: AzurePreCallSecurityExecutor
    operation_start: OperationStartExecutor
    execution_binding: DomainExecutionBinding
    post_operation_observation: AzureVmPostOperationObservationExecutor

    def __post_init__(self) -> None:
        execution_path = DomainExecutionPath(
            execution_binding=self.execution_binding,
            executors=(
                self.pre_call,
                self.operation_start,
                self.execution_binding.executor,
            ),
        )
        object.__setattr__(
            self,
            "_execution_path",
            execution_path,
        )

    @property
    def execution_path(self) -> DomainExecutionPath:
        """Devuelve la instancia declarada al construir la composicion."""
        return self._execution_path


def build_azure_domain_composition(
    *,
    agents: FoundryAgents,
    operation_dispatch_ledger: OperationDispatchLedger,
    wait_recheck_consumption_ledger: WaitRecheckConsumptionLedger,
    azure_vm_power_state_reader: AzureVmPowerStateReader | None = None,
    capability_foundry_agent_binding_registry: CapabilityFoundryAgentBindingRegistry | None = None,
    vm_start_route: GovernedVmStartRoute | None = None,
    attestation_publisher=None,
    azure_read_tool_authority_registry: AzureReadToolAuthorityRegistry | None = None,
) -> AzureDomainComposition:
    """Construye nodos nuevos con dependencias suministradas por el caller.

    Las tres dependencias obligatorias se comprueban antes de crear nodos.
    El lector opcional conserva None; no se crea un cliente por defecto.
    No ejecuta handlers, registra capabilities, construye aristas ni conecta
    el resultado al workflow. Pre-call, lifecycle, dispatch y WAIT conservan
    sus implementaciones existentes y sus fronteras separadas.
    """
    if agents is None:
        raise ValueError("agents no puede ser None.")
    if operation_dispatch_ledger is None:
        raise ValueError("operation_dispatch_ledger no puede ser None.")
    if wait_recheck_consumption_ledger is None:
        raise ValueError("wait_recheck_consumption_ledger no puede ser None.")

    if (
        capability_foundry_agent_binding_registry is not None
        and not isinstance(
            capability_foundry_agent_binding_registry,
            CapabilityFoundryAgentBindingRegistry,
        )
    ):
        raise TypeError("Invalid capability Foundry agent binding registry.")

    pre_call = AzurePreCallSecurityExecutor()
    operation_start = OperationStartExecutor()
    selector_options = {}
    if azure_read_tool_authority_registry is not None:
        if not isinstance(azure_read_tool_authority_registry, AzureReadToolAuthorityRegistry):
            raise TypeError("Invalid READ authority registry.")
        selector_options["azure_read_tool_authority_registry"] = azure_read_tool_authority_registry
    if attestation_publisher is not None:
        from src.attestation.governor_outbox import GovernorAttestationPublisher
        if type(attestation_publisher) is not GovernorAttestationPublisher:
            raise TypeError("Explicit governor attestation publisher required")
        selector_options["attestation_publisher"] = attestation_publisher
    if vm_start_route is not None:
        if not isinstance(vm_start_route, GovernedVmStartRoute):
            raise TypeError("vm_start_route must be GovernedVmStartRoute.")
        selector_options["vm_start_route"] = vm_start_route
    if capability_foundry_agent_binding_registry is not None:
        selector_options["capability_foundry_agent_binding_registry"] = (
            capability_foundry_agent_binding_registry
        )
    operations = AzureOperationsExecutor(
        agents=agents,
        operation_dispatch_ledger=operation_dispatch_ledger,
        **selector_options,
    )
    execution_binding = DomainExecutionBinding(
        operation_domain="azure",
        executor_id="azure_operations",
        executor=operations,
    )
    observation = AzureVmPostOperationObservationExecutor(
        reader=azure_vm_power_state_reader,
        wait_recheck_consumption_ledger=wait_recheck_consumption_ledger,
    )

    return AzureDomainComposition(
        pre_call=pre_call,
        operation_start=operation_start,
        execution_binding=execution_binding,
        post_operation_observation=observation,
    )
