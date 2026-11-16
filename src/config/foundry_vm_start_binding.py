"""Explicit, local publication configuration for the isolated VM_START route.

This builder does not read the process environment, query Azure, verify a
publication or grant execution authority. Its values belong to trusted host
configuration populated from publication GET evidence. A connection reference
is the observed connection NAME, not an assumed ARM or opaque data-plane ID.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from urllib.parse import urlsplit

from src.agents.catalog import AgentKey, FoundryAgentDefinition
from src.workflows.incident_resolution.vm_start_foundry_binding import (
    VmStartFoundryBinding,
)


PROFILE_ENVIRONMENT_KEY = "FOUNDRY_VM_START_BINDING_PROFILE"
ISOLATED_VM_START_PROFILE = "azure-vm-start-isolated-v1"
PUBLICATION_KEYS = (
    "FOUNDRY_VM_START_AGENT_NAME",
    "FOUNDRY_VM_START_AGENT_VERSION",
    "FOUNDRY_VM_START_CONNECTION_REFERENCE",
    "FOUNDRY_VM_START_SERVER_URL",
    "FOUNDRY_VM_START_SERVER_LABEL",
)
_RESERVED_AGENTS = frozenset((
    "agent-azure-operations-sbx", "agent-azure-operations-rg-list-sbx",
))
_RESERVED_CONNECTIONS = frozenset((
    "azure-mcp-operations-sbx", "azure-mcp-rglist-read-sbx",
))
_RESERVED_LABELS = frozenset((
    "azure-mcp-operations-sbx", "azure-mcp-rglist-read",
))
_RESERVED_HOST_NAMES = frozenset((
    "azure-mcp-operations-server", "azure-mcp-rglist-read-sbx",
))


def _exact_text(environment: Mapping[str, object], name: str) -> str:
    value = environment.get(name)
    if (type(value) is not str or not value or value != value.strip()
            or any(ord(character) < 32 for character in value)):
        raise ValueError(f"{name} must be an exact non-empty publication value.")
    return value


def _dedicated_name(value: str, reserved: frozenset[str], field: str) -> None:
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)
            or value.casefold() in reserved
            or re.search(r"(?:^|[-_])poc(?:$|[-_])", value, re.IGNORECASE)):
        raise ValueError(f"{field} must identify a dedicated non-POC WRITE component.")


def build_vm_start_foundry_binding(
    environment: Mapping[str, object],
) -> VmStartFoundryBinding | None:
    """No opt-in keeps legacy wiring; invalid/partial opt-in never falls back."""
    if not isinstance(environment, Mapping):
        raise TypeError("environment must implement Mapping.")
    if PROFILE_ENVIRONMENT_KEY not in environment:
        if any(key in environment for key in PUBLICATION_KEYS):
            raise ValueError("VM_START publication values require the explicit profile.")
        return None
    if (type(environment[PROFILE_ENVIRONMENT_KEY]) is not str
            or environment[PROFILE_ENVIRONMENT_KEY] != ISOLATED_VM_START_PROFILE):
        raise ValueError("FOUNDRY_VM_START_BINDING_PROFILE is not an admitted exact profile.")

    values = {key: _exact_text(environment, key) for key in PUBLICATION_KEYS}
    endpoint = _exact_text(environment, "FOUNDRY_PROJECT_ENDPOINT")
    name = values["FOUNDRY_VM_START_AGENT_NAME"]
    connection = values["FOUNDRY_VM_START_CONNECTION_REFERENCE"]
    label = values["FOUNDRY_VM_START_SERVER_LABEL"]
    _dedicated_name(name, _RESERVED_AGENTS, "agent_name")
    _dedicated_name(connection, _RESERVED_CONNECTIONS, "connection_name")
    _dedicated_name(label, _RESERVED_LABELS, "server_label")

    # Reuse the existing binding's exact version/HTTPS/root checks. No version,
    # server URL, tenant value or connection reference is synthesized here.
    binding = VmStartFoundryBinding(
        agent_definition=FoundryAgentDefinition(
            key=AgentKey.AZURE_OPERATIONS,
            name=name,
            version=values["FOUNDRY_VM_START_AGENT_VERSION"],
        ),
        project_endpoint=endpoint,
        project_connection_id=connection,
        server_url=values["FOUNDRY_VM_START_SERVER_URL"],
        server_label=label,
        require_approval="always",
    )
    host_name = urlsplit(binding.server_url).hostname.split(".", 1)[0]
    _dedicated_name(host_name, _RESERVED_HOST_NAMES, "server_hostname")
    return binding
