"""Configuracion explicita de bindings Foundry ya revisadas.

El perfil selecciona un descriptor mediante los contratos de Python existentes.
No consulta Foundry, concede HITL, comprueba RBAC ni ejecuta herramientas MCP.
La conexion y la politica publicadas se acreditan en el expediente de la
definicion versionada; este builder no vuelve a verificarlas remotamente.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import re

from src.agents.catalog import AgentKey, FoundryAgentDefinition
from src.workflows.incident_resolution.azure_read_tool_authority import (
    build_default_azure_read_tool_authority_registry,
)
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBinding,
    CapabilityFoundryAgentBindingRegistry,
)
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)


PROFILE_ENVIRONMENT_KEY = "FOUNDRY_CAPABILITY_BINDING_PROFILE"
RESOURCE_GROUP_LIST_SANDBOX_PROFILE = "azure-resource-group-list-sbx-v1"
RESOURCE_GROUP_LIST_ISOLATED_PROFILE = "azure-resource-group-list-isolated-v1"
ISOLATED_VERSION_KEY = "FOUNDRY_RG_LIST_AGENT_VERSION"
RESOURCE_GROUP_LIST_CAPABILITY_ID = "azure.resource_group.list"
SANDBOX_PROJECT_ENDPOINT = (
    "https://aif-icenter-sbx-eus2.services.ai.azure.com/"
    "api/projects/aifproj-icenter-sbx"
)


def build_capability_foundry_agent_binding_registry(
    environment: Mapping[str, object],
) -> CapabilityFoundryAgentBindingRegistry:
    """Materializa el perfil exacto; su ausencia mantiene el selector vacio.

    No lee os.environ ni modifica el mapping recibido. Un perfil presente pero
    invalido no se convierte en ausencia ni recurre al agente general.
    """
    if not isinstance(environment, Mapping):
        raise TypeError("environment debe implementar Mapping.")

    if PROFILE_ENVIRONMENT_KEY not in environment:
        if ISOLATED_VERSION_KEY in environment:
            raise ValueError("READ publication requires its explicit isolated profile.")
        return CapabilityFoundryAgentBindingRegistry(bindings=())

    profile = environment[PROFILE_ENVIRONMENT_KEY]
    if (
        type(profile) is not str
        or profile not in (RESOURCE_GROUP_LIST_SANDBOX_PROFILE, RESOURCE_GROUP_LIST_ISOLATED_PROFILE)
    ):
        raise ValueError(
            "FOUNDRY_CAPABILITY_BINDING_PROFILE no identifica un perfil exacto admitido."
        )

    endpoint = environment.get("FOUNDRY_PROJECT_ENDPOINT")
    if type(endpoint) is not str or endpoint != SANDBOX_PROJECT_ENDPOINT:
        raise ValueError(
            "FOUNDRY_PROJECT_ENDPOINT no coincide con el proyecto del perfil revisado."
        )

    authority = build_default_azure_read_tool_authority_registry().get(RESOURCE_GROUP_LIST_CAPABILITY_ID)
    version = "1"
    if profile == RESOURCE_GROUP_LIST_ISOLATED_PROFILE:
        version = environment.get(ISOLATED_VERSION_KEY)
        if type(version) is not str or not re.fullmatch(r"[1-9][0-9]*", version) or version in {"1", "2"}:
            raise ValueError("READ requires an observed isolated version; legacy v1 and rejected v2 are excluded.")
        authority = replace(authority, server_label="azure-mcp-rglist-read")
    elif ISOLATED_VERSION_KEY in environment:
        raise ValueError("Isolated READ version cannot be combined with the legacy profile.")

    binding = CapabilityFoundryAgentBinding(
        capability=build_default_capability_registry().get(
            RESOURCE_GROUP_LIST_CAPABILITY_ID
        ),
        read_tool_authority=authority,
        agent_definition=FoundryAgentDefinition(
            key=AgentKey.AZURE_OPERATIONS,
            name="agent-azure-operations-rg-list-sbx",
            version=version,
        ),
        require_approval="always",
    )
    return CapabilityFoundryAgentBindingRegistry(bindings=(binding,))
