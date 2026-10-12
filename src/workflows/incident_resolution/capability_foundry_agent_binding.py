"""Binding declarativo exacto entre una capability READ y un agente Foundry.

El binding es autoridad de seleccion Python, NO autorizacion operacional:
no valida estado LIVE, RBAC, identidad, conexiones, HITL ni ejecuta MCP.
No existe binding por defecto para RG List en esta fase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from src.agents.catalog import AgentKey, FoundryAgentDefinition
from src.runtime.procedure.models import OperationKind
from .azure_read_tool_authority import AzureReadToolAuthority
from .operational_capability import OperationalCapability


class CapabilityFoundryAgentBindingError(ValueError):
    """La declaracion o resolucion no coincide con la autoridad exacta."""


class CapabilityFoundryAgentBindingRegistryError(ValueError):
    """El registro no permite resolver un binding exacto y unico."""


@dataclass(frozen=True)
class CapabilityFoundryAgentBinding:
    """Une una capability READ a un agente versionado y a su autoridad MCP.

    Esta declaracion no certifica la politica efectiva del agente LIVE.
    La admision LIVE y el dispatcher permanecen bloqueados por separado.
    """

    capability: OperationalCapability
    read_tool_authority: AzureReadToolAuthority
    agent_definition: FoundryAgentDefinition
    require_approval: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability, OperationalCapability):
            raise CapabilityFoundryAgentBindingError(
                "capability debe ser OperationalCapability."
            )
        if not isinstance(self.read_tool_authority, AzureReadToolAuthority):
            raise CapabilityFoundryAgentBindingError(
                "read_tool_authority debe ser AzureReadToolAuthority."
            )
        if not isinstance(self.agent_definition, FoundryAgentDefinition):
            raise CapabilityFoundryAgentBindingError(
                "agent_definition debe ser FoundryAgentDefinition."
            )
        if self.agent_definition.key != AgentKey.AZURE_OPERATIONS:
            raise CapabilityFoundryAgentBindingError(
                "El rol Foundry no es Azure Operations."
            )
        if not re.fullmatch(
            r"agent-[a-z0-9]+(?:-[a-z0-9]+)*", self.agent_definition.name
        ):
            raise CapabilityFoundryAgentBindingError(
                "El nombre de agente debe ser exacto y sin alias."
            )
        if not re.fullmatch(r"[1-9][0-9]*", self.agent_definition.version):
            raise CapabilityFoundryAgentBindingError(
                "La version debe ser explicita y numerica; latest prohibido."
            )
        if self.require_approval != "always":
            raise CapabilityFoundryAgentBindingError(
                "La declaracion READ gobernada exige approval MCP always."
            )
        self._verify_capability_and_authority(
            self.capability, self.read_tool_authority
        )

    @staticmethod
    def _verify_capability_and_authority(
        capability: OperationalCapability,
        authority: AzureReadToolAuthority,
    ) -> None:
        if (
            capability.operation_domain != "azure"
            or capability.operation_kind != OperationKind.READ
            or capability.executor_id != "azure_operations"
            or authority.operation_domain != "azure"
            or capability.capability_id != authority.capability_id
            or capability.resource_type != authority.resource_type
            or capability.operation_action != authority.operation_action
            or capability.required_parameters != authority.required_parameters
        ):
            raise CapabilityFoundryAgentBindingError(
                "Capability y autoridad MCP READ no coinciden exactamente."
            )

    def resolve(
        self,
        *,
        capability: OperationalCapability,
        read_tool_authority: AzureReadToolAuthority,
    ) -> FoundryAgentDefinition:
        """Devuelve el descriptor fijado; no crea ni invoca un agente."""
        if (
            not isinstance(capability, OperationalCapability)
            or not isinstance(read_tool_authority, AzureReadToolAuthority)
            or capability != self.capability
            or read_tool_authority != self.read_tool_authority
        ):
            raise CapabilityFoundryAgentBindingError(
                "Resolucion de capability o tool MCP distinta del binding."
            )
        self._verify_capability_and_authority(capability, read_tool_authority)
        return self.agent_definition


class CapabilityFoundryAgentBindingRegistry:
    """Registro inmutable; no hay seleccion implicita ni fallback a v13."""

    def __init__(
        self,
        *,
        bindings: Iterable[CapabilityFoundryAgentBinding],
    ) -> None:
        selected: dict[str, CapabilityFoundryAgentBinding] = {}
        for binding in bindings:
            if not isinstance(binding, CapabilityFoundryAgentBinding):
                raise CapabilityFoundryAgentBindingRegistryError(
                    "Solo se admiten CapabilityFoundryAgentBinding."
                )
            key = binding.capability.capability_id
            if key in selected:
                raise CapabilityFoundryAgentBindingRegistryError(
                    "capability_id duplicada en el registro de agentes."
                )
            selected[key] = binding
        self._bindings: Mapping[str, CapabilityFoundryAgentBinding] = (
            MappingProxyType(selected)
        )

    def get(self, capability_id: str) -> CapabilityFoundryAgentBinding:
        if not isinstance(capability_id, str) or not capability_id:
            raise CapabilityFoundryAgentBindingRegistryError(
                "capability_id debe ser un identificador exacto."
            )
        try:
            return self._bindings[capability_id]
        except KeyError:
            raise CapabilityFoundryAgentBindingRegistryError(
                "No existe binding de agente Foundry para esta capability."
            ) from None

    def resolve(
        self,
        *,
        capability: OperationalCapability,
        read_tool_authority: AzureReadToolAuthority,
    ) -> FoundryAgentDefinition:
        if not isinstance(capability, OperationalCapability):
            raise CapabilityFoundryAgentBindingRegistryError(
                "capability debe ser OperationalCapability."
            )
        return self.get(capability.capability_id).resolve(
            capability=capability,
            read_tool_authority=read_tool_authority,
        )

    def count(self) -> int:
        return len(self._bindings)
