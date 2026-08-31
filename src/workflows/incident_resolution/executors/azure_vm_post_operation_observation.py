from __future__ import annotations

import asyncio

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from ..azure_vm_instance_view import (
    AzureVmPowerStateReader,
)

from ..post_operation_observation import (
    AzureVmPowerStateObservation,
)

from ..procedure_validation_models import (
    ProcedureValidationRequest,
)


class AzureVmPostOperationObservationExecutor(
    Executor
):
    """
    Frontera determinista read-only entre el
    resultado WRITE registrado y Procedure Validation.
    """

    def __init__(
        self,
        reader: AzureVmPowerStateReader | None = None,
    ) -> None:
        super().__init__(
            id="azure_vm_post_operation_observation"
        )

        self._reader = reader

    @staticmethod
    def _revalidate_request(
        request: ProcedureValidationRequest,
    ) -> ProcedureValidationRequest:
        return (
            ProcedureValidationRequest
            .model_validate(
                request.model_dump(
                    mode="python"
                )
            )
        )

    @staticmethod
    def _requires_vm_observation(
        request: ProcedureValidationRequest,
    ) -> bool:
        result = request.operation_result

        return (
            result.operation_domain
            == "azure"
            and
            result.operation_kind
            == OperationKind.WRITE
            and
            result.operation_action
            == OperationAction.VM_START
            and
            result.capability_id
            == "azure.vm.start"
            and
            result.hitl_required
            is True
        )

    @staticmethod
    def _resolved_vm_identity(
        request: ProcedureValidationRequest,
    ) -> dict[str, str]:
        result = request.operation_result

        names = [
            parameter.name
            for parameter
            in result.resolved_parameters
        ]

        if len(names) != len(set(names)):
            raise ValueError(
                "Resolved parameters contiene "
                "nombres duplicados."
            )

        resolved = {
            parameter.name:
                parameter.value
            for parameter
            in result.resolved_parameters
        }

        expected_names = {
            "subscription_id",
            "resource_group",
            "vm_name",
        }

        if set(resolved) != expected_names:
            raise ValueError(
                "VM Start post-operation observation "
                "requiere exactamente "
                "subscription_id, resource_group "
                "y vm_name."
            )

        if (
            not isinstance(
                result.target_resource,
                str,
            )
            or not result.target_resource
        ):
            raise ValueError(
                "VM Start requiere target_resource."
            )

        expected_target = (
            "/subscriptions/"
            f"{resolved['subscription_id']}"
            "/resourceGroups/"
            f"{resolved['resource_group']}"
            "/providers/Microsoft.Compute/"
            "virtualMachines/"
            f"{resolved['vm_name']}"
        )

        if (
            result.target_resource.casefold()
            != expected_target.casefold()
        ):
            raise ValueError(
                "Target resource no corresponde "
                "a los parámetros gobernados."
            )

        return resolved

    @staticmethod
    def _build_observation(
        *,
        request: ProcedureValidationRequest,
        resolved: dict[str, str],
        success: bool,
        power_state: str | None,
        error: str | None,
    ) -> AzureVmPowerStateObservation:
        result = request.operation_result

        return AzureVmPowerStateObservation(
            operation_id=result.operation_id,
            workflow_id=result.workflow_id,
            approval_id=result.approval_id,
            target_resource=result.target_resource,
            subscription_id=resolved["subscription_id"],
            resource_group=resolved["resource_group"],
            vm_name=resolved["vm_name"],
            success=success,
            power_state=power_state,
            error=error,
        )

    @handler
    async def handle(
        self,
        request: ProcedureValidationRequest,
        ctx: WorkflowContext[
            ProcedureValidationRequest
        ],
    ) -> None:
        trusted_request = (
            self._revalidate_request(
                request
            )
        )

        result = trusted_request.operation_result

        if not self._requires_vm_observation(
            trusted_request
        ):
            await ctx.send_message(
                trusted_request
            )
            return

        if (
            result.success is not True
            or result.technical_success is not True
        ):
            await ctx.send_message(
                trusted_request
            )
            return

        resolved = (
            self._resolved_vm_identity(
                trusted_request
            )
        )

        try:
            if self._reader is None:
                raise RuntimeError(
                    "Azure VM power-state reader "
                    "no está configurado."
                )

            power_state = (
                await asyncio.to_thread(
                    self._reader.read_power_state,
                    subscription_id=resolved["subscription_id"],
                    resource_group=resolved["resource_group"],
                    vm_name=resolved["vm_name"],
                )
            )

            observation = (
                self._build_observation(
                    request=trusted_request,
                    resolved=resolved,
                    success=True,
                    power_state=power_state,
                    error=None,
                )
            )

        except Exception as exc:
            observation = (
                self._build_observation(
                    request=trusted_request,
                    resolved=resolved,
                    success=False,
                    power_state=None,
                    error=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )
            )

        enriched_request = (
            ProcedureValidationRequest(
                operation_result=trusted_request.operation_result,
                step=trusted_request.step,
                post_operation_observation=observation,
            )
        )

        await ctx.send_message(
            enriched_request
        )
