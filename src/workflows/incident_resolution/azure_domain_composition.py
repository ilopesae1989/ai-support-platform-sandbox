from __future__ import annotations

from dataclasses import dataclass

from src.agents.foundry_agents import FoundryAgents

from .azure_vm_instance_view import AzureVmPowerStateReader
from .domain_execution_binding import DomainExecutionBinding
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


def build_azure_domain_composition(
    *,
    agents: FoundryAgents,
    operation_dispatch_ledger: OperationDispatchLedger,
    wait_recheck_consumption_ledger: WaitRecheckConsumptionLedger,
    azure_vm_power_state_reader: AzureVmPowerStateReader | None = None,
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

    pre_call = AzurePreCallSecurityExecutor()
    operation_start = OperationStartExecutor()
    operations = AzureOperationsExecutor(
        agents=agents,
        operation_dispatch_ledger=operation_dispatch_ledger,
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
