"""Productive opt-in for the exact isolated WRITE descriptor.

The existing FoundryAgents begin/continue, session correlation and credential
selection remain unchanged. Only creation of the configured WRITE descriptor
uses the explicit v1 agent endpoint adapter; all other descriptors use super.
No provider is invoked while this module is imported.
"""
from __future__ import annotations

from src.agents.catalog import FoundryAgentDefinition
from src.agents.foundry_agents import FoundryAgents
from src.agents.production_credential import build_foundry_production_credential
from src.agents.production_settings import FoundryProductionSettings
from src.agents.vm_start_agent_endpoint import build_vm_start_agent_endpoint
from src.workflows.incident_resolution.vm_start_foundry_binding import (
    VmStartFoundryBinding,
)


class IsolatedVmStartFoundryAgents(FoundryAgents):
    def __init__(
        self, *, project_endpoint: str, credential: object,
        vm_start_binding: VmStartFoundryBinding,
        catalog=None,
        deployment_fingerprint=None,
    ) -> None:
        if not isinstance(vm_start_binding, VmStartFoundryBinding):
            raise TypeError("An explicit VM_START binding is required.")
        if project_endpoint != vm_start_binding.project_endpoint:
            raise ValueError("The production project differs from the WRITE binding.")
        if credential is None:
            raise ValueError("The productive WRITE route requires an injected credential.")
        self._vm_start_binding = vm_start_binding
        super().__init__(
            project_endpoint=project_endpoint, credential=credential,
            # Preserve the existing cognitive-agent configuration. The new
            # WRITE adapter explicitly sets allow_preview=False/API v1.
            allow_preview=True,
            **({"catalog": catalog} if catalog is not None else {}),
            **({"deployment_fingerprint": deployment_fingerprint} if deployment_fingerprint is not None else {}),
        )

    def _create_agent(self, definition: FoundryAgentDefinition):
        if definition.name == self._vm_start_binding.agent_definition.name:
            if definition != self._vm_start_binding.agent_definition:
                raise ValueError("The isolated WRITE descriptor differs from its pinned publication.")
            return build_vm_start_agent_endpoint(
                definition=definition,
                project_endpoint=self.project_endpoint,
                credential=self._credential,
            )
        return super()._create_agent(definition)


def build_vm_start_production_agents(
    settings: FoundryProductionSettings, *, vm_start_binding: VmStartFoundryBinding,
    catalog=None,
    deployment_fingerprint=None,
) -> IsolatedVmStartFoundryAgents:
    if not isinstance(settings, FoundryProductionSettings):
        raise TypeError("settings must be FoundryProductionSettings.")
    # Same production credential builder; no CLI or user credential fallback.
    credential = build_foundry_production_credential(settings)
    return IsolatedVmStartFoundryAgents(
        project_endpoint=settings.project_endpoint, credential=credential,
        vm_start_binding=vm_start_binding,
        **({"catalog": catalog} if catalog is not None else {}),
        **({"deployment_fingerprint": deployment_fingerprint} if deployment_fingerprint is not None else {}),
    )
