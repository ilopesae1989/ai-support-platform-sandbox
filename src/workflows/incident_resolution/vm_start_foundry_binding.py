"""Explicit VM_START route; selection is not network authorization.

The publication descriptor must come from verified deployment evidence.
The approval binding reader is deliberately read-only and has no default
implementation. Its snapshot must have been bound to the existing trusted
approval/checkpoint BEFORE HITL. No hash supplied in a user message, model
output or MCP argument can satisfy this contract. This module neither
implements that persistence integration nor transmits a grant to MCP.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlsplit

from src.agents.catalog import AgentKey, FoundryAgentDefinition
from src.runtime.procedure.models import NextAction, OperationAction, OperationKind

if TYPE_CHECKING:
    from .azure_operations_models import VerifiedAzureOperationRequest


class VmStartBindingError(ValueError):
    pass


def _exact_text(value: object, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise VmStartBindingError(f"{field} must be an exact non-empty string.")
    if any(ord(character) < 32 for character in value):
        raise VmStartBindingError(f"{field} contains a control character.")
    return value


@dataclass(frozen=True)
class VmStartFoundryBinding:
    agent_definition: FoundryAgentDefinition
    project_endpoint: str
    project_connection_id: str
    server_url: str
    server_label: str
    require_approval: str = "always"

    def __post_init__(self) -> None:
        definition = self.agent_definition
        if not isinstance(definition, FoundryAgentDefinition):
            raise VmStartBindingError("A FoundryAgentDefinition is required.")
        if definition.key != AgentKey.AZURE_OPERATIONS:
            raise VmStartBindingError("The descriptor must be Azure Operations.")
        if type(definition.name) is not str or not re.fullmatch(
            r"agent-[a-z0-9]+(?:-[a-z0-9]+)*", definition.name
        ):
            raise VmStartBindingError("The agent name must be explicit.")
        if type(definition.version) is not str or not re.fullmatch(
            r"[1-9][0-9]*", definition.version
        ):
            raise VmStartBindingError("The observed version must be pinned.")
        for field in ("project_endpoint", "project_connection_id", "server_url", "server_label"):
            _exact_text(getattr(self, field), field)
        if self.require_approval != "always":
            raise VmStartBindingError("VM_START requires MCP approval always.")
        for field in ("project_endpoint", "server_url"):
            value = urlsplit(getattr(self, field))
            if (value.scheme != "https" or not value.hostname
                    or value.username is not None or value.password is not None
                    or value.query or value.fragment or value.port not in (None, 443)):
                raise VmStartBindingError(f"{field} must be exact HTTPS without credentials.")
            if field == "server_url" and value.path not in ("", "/"):
                raise VmStartBindingError("The verified MCP root must be explicit.")

    @property
    def fingerprint(self) -> str:
        # Connection/URL are publication assertions, not fields supplied by
        # a pending MCP approval. They must also be checked by deployment GETs.
        data = {
            "schema": "vm-start-foundry-binding/four-arguments-v1",
            "capability_id": "azure.vm.start",
            "agent_key": self.agent_definition.key.value,
            "agent_name": self.agent_definition.name,
            "agent_version": self.agent_definition.version,
            "project_endpoint": self.project_endpoint,
            "project_connection_id": self.project_connection_id,
            "server_url": self.server_url,
            "server_label": self.server_label,
            "require_approval": self.require_approval,
        }
        raw = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("ascii")).hexdigest()

    @staticmethod
    def validate_request(request: VerifiedAzureOperationRequest) -> None:
        # Called only after the existing VerifiedAzureOperationRequest
        # revalidation. This adds no new authority to that Python object.
        if (request.operation_domain != "azure"
                or request.operation_kind != OperationKind.WRITE
                or request.operation_action != OperationAction.VM_START
                or request.capability_id != "azure.vm.start"
                or request.hitl_required is not True
                or request.next_action != NextAction.EXECUTE_STEP
                or request.security_verified is not True
                or request.verification_source != "pre_call_security_verifier"):
            raise VmStartBindingError("The route accepts only governed VM_START.")
        names = tuple(parameter.name for parameter in request.resolved_parameters)
        expected = ("subscription_id", "resource_group", "vm_name")
        if tuple(request.required_parameters) != expected or names != expected:
            raise VmStartBindingError("VM_START requires the exact canonical parameters.")
        resolved = {
            parameter.name: _exact_text(parameter.value, parameter.name)
            for parameter in request.resolved_parameters
        }
        target = (f"/subscriptions/{resolved['subscription_id']}"
                  f"/resourceGroups/{resolved['resource_group']}"
                  f"/providers/Microsoft.Compute/virtualMachines/{resolved['vm_name']}")
        if type(request.target_resource) is not str or request.target_resource.casefold() != target.casefold():
            raise VmStartBindingError("VM_START target differs from the approved parameters.")


@dataclass(frozen=True)
class ApprovedVmStartBindingSnapshot:
    workflow_id: str
    approval_id: str
    operation_id: str
    binding_fingerprint: str

    def __post_init__(self) -> None:
        for field in ("workflow_id", "approval_id", "operation_id"):
            _exact_text(getattr(self, field), field)
        if type(self.binding_fingerprint) is not str or not re.fullmatch(
            r"[0-9a-f]{64}", self.binding_fingerprint
        ):
            raise VmStartBindingError("The persisted binding fingerprint is invalid.")


class ApprovedVmStartBindingReader(Protocol):
    """Adapter to trusted EXISTING approval persistence; no parallel ledger.

    The adapter must verify the record belongs to the approved workflow/step
    and read a binding snapshot recorded before HITL, with the existing
    integrity/authorization checks. It must not manufacture the snapshot from
    the current configuration, request, user input or a model response.
    Missing/old approvals without this snapshot must return None or raise.
    """
    async def read_approved_vm_start_binding(
        self, *, workflow_id: str, approval_id: str, operation_id: str
    ) -> ApprovedVmStartBindingSnapshot | None: ...


@dataclass(frozen=True)
class GovernedVmStartRoute:
    binding: VmStartFoundryBinding
    approval_binding_reader: ApprovedVmStartBindingReader

    def __post_init__(self) -> None:
        if not isinstance(self.binding, VmStartFoundryBinding):
            raise VmStartBindingError("An explicit VM_START binding is required.")
        if not callable(getattr(self.approval_binding_reader, "read_approved_vm_start_binding", None)):
            raise VmStartBindingError("A trusted approval binding reader is required.")

    async def resolve_for(
        self, request: VerifiedAzureOperationRequest, *, project_endpoint: str
    ) -> VmStartFoundryBinding:
        self.binding.validate_request(request)
        if project_endpoint != self.binding.project_endpoint:
            raise VmStartBindingError("The Foundry project differs from the binding.")
        snapshot = await self.approval_binding_reader.read_approved_vm_start_binding(
            workflow_id=request.workflow_id,
            approval_id=request.approval_id,
            operation_id=request.operation_id,
        )
        if type(snapshot) is not ApprovedVmStartBindingSnapshot:
            raise VmStartBindingError("No trusted approved binding snapshot is available.")
        if ((snapshot.workflow_id, snapshot.approval_id, snapshot.operation_id)
                != (request.workflow_id, request.approval_id, request.operation_id)
                or snapshot.binding_fingerprint != self.binding.fingerprint):
            raise VmStartBindingError("Approved/restored VM_START binding differs from the active route.")
        return self.binding
