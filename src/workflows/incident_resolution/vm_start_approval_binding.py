"""Read a pre-HITL WRITE binding from the existing approval/checkpoint stores.

This is a read-only guard, not an authority or consumption ledger. The trusted
host must protect both stores as it already does for approval resumption.
No fingerprint is accepted from the request/channel/model or recomputed from
current deployment configuration here. SQL schemas and dispatch claims stay
unchanged; the same implementation works with the existing local stores.
"""
from __future__ import annotations

from src.runtime.procedure.identity import create_operation_id
from src.runtime.procedure.models import (
    ApprovalStatus, OperationAction, OperationKind, ProcedureRuntimeState,
    StepStatus, WorkflowStatus,
)
from src.runtime.procedure.workflow_state import PROCEDURE_RUNTIME_STATE_KEY
from .vm_start_foundry_binding import ApprovedVmStartBindingSnapshot, VmStartBindingError


def _text(value: object, field: str) -> str:
    if (type(value) is not str or not value or value != value.strip()
            or any(ord(char) < 32 for char in value)):
        raise VmStartBindingError(f"{field} must be an exact non-empty string.")
    return value


class CheckpointApprovedVmStartBindingReader:
    def __init__(self, *, store: object, checkpoint_storage: object,
                 workflow_name: str = "incident-resolution") -> None:
        for method in ("get_by_approval_id", "get_by_request_id", "get_consumption_record"):
            if not callable(getattr(store, method, None)):
                raise TypeError(f"The existing approval store must implement {method}.")
        if not callable(getattr(checkpoint_storage, "load", None)):
            raise TypeError("The existing checkpoint storage must implement load.")
        self._store = store
        self._checkpoint_storage = checkpoint_storage
        self._workflow_name = _text(workflow_name, "workflow_name")

    async def read_approved_vm_start_binding(
        self, *, workflow_id: str, approval_id: str, operation_id: str
    ) -> ApprovedVmStartBindingSnapshot:
        _text(workflow_id, "workflow_id")
        _text(approval_id, "approval_id")
        _text(operation_id, "operation_id")
        correlation = self._store.get_by_approval_id(approval_id)
        if (correlation.workflow_id != workflow_id
                or correlation.approval_id != approval_id
                or self._store.get_by_request_id(correlation.request_id) != correlation):
            raise VmStartBindingError("The durable HITL correlation does not match.")
        decision = self._store.get_consumption_record(approval_id)
        if (type(decision) is not tuple or len(decision) != 2
                or decision[0] not in ("claimed", "completed")
                or decision[1] is not True):
            raise VmStartBindingError("No consumed positive HITL decision exists.")

        checkpoint = await self._checkpoint_storage.load(correlation.checkpoint_id)
        if (getattr(checkpoint, "checkpoint_id", None) != correlation.checkpoint_id
                or getattr(checkpoint, "workflow_name", None) != self._workflow_name):
            raise VmStartBindingError("The exact approval checkpoint was not returned.")
        checkpoint_state = getattr(checkpoint, "state", None)
        if type(checkpoint_state) is not dict:
            raise VmStartBindingError("The approval checkpoint has no exact state mapping.")
        payload = checkpoint_state.get(PROCEDURE_RUNTIME_STATE_KEY)
        if type(payload) is not dict:
            raise VmStartBindingError("The approval checkpoint has no governed state snapshot.")
        state = ProcedureRuntimeState.model_validate(payload)
        if (state.model_dump(mode="json") != payload
                or state.vm_start_binding_fingerprint is None):
            raise VmStartBindingError("The pre-HITL binding snapshot is absent or noncanonical.")
        step = state.step
        if (state.workflow_id != workflow_id or state.approval_id != approval_id
                or state.step_status != StepStatus.WAITING_APPROVAL
                or state.approval_status != ApprovalStatus.PENDING
                or state.workflow_status != WorkflowStatus.WAITING_HUMAN
                or step.operation_domain != "azure"
                or step.operation_kind != OperationKind.WRITE
                or step.operation_action != OperationAction.VM_START
                or step.capability_id != "azure.vm.start"
                or step.hitl_required is not True):
            raise VmStartBindingError("The persisted snapshot is not the pending VM_START approval.")
        expected = ("subscription_id", "resource_group", "vm_name")
        if (tuple(step.required_parameters) != expected
                or tuple(parameter.name for parameter in state.resolved_parameters) != expected):
            raise VmStartBindingError("The persisted VM_START parameters are not exact.")
        parameters = {parameter.name: _text(parameter.value, parameter.name)
                      for parameter in state.resolved_parameters}
        for parameter in state.resolved_parameters:
            _text(parameter.source, "parameter_source")
        target = (f"/subscriptions/{parameters['subscription_id']}"
                  f"/resourceGroups/{parameters['resource_group']}"
                  f"/providers/Microsoft.Compute/virtualMachines/{parameters['vm_name']}")
        if _text(step.target_resource, "target_resource").casefold() != target.casefold():
            raise VmStartBindingError("The persisted VM_START target is inconsistent.")
        persisted_operation_id = create_operation_id(
            workflow_id=state.workflow_id, approval_id=state.approval_id,
            alert_id=state.alert_id, procedure_id=state.procedure.id,
            current_step=state.current_step, step_id=step.id,
        )
        if persisted_operation_id != operation_id:
            raise VmStartBindingError("The operation does not belong to the approved step.")
        if (self._store.get_by_approval_id(approval_id) != correlation
                or self._store.get_consumption_record(approval_id) != decision):
            raise VmStartBindingError("The durable approval changed during checkpoint loading.")
        return ApprovedVmStartBindingSnapshot(
            workflow_id=workflow_id, approval_id=approval_id,
            operation_id=persisted_operation_id,
            binding_fingerprint=state.vm_start_binding_fingerprint,
        )
