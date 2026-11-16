"""Trusted per-deployment Foundry configuration; no provider calls or publication.

The host owns this document. Incident/model/tool data must never supply it.
Connection/root declarations require deployment readback; parsing is not proof
of their effective server-side configuration, identity or permissions.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import json
import hashlib
import re
from types import MappingProxyType
from urllib.parse import urlsplit

from src.agents.catalog import AgentKey, FoundryAgentDefinition, AGENT_VERSION_ENV_VARS
from src.config.foundry_capability_bindings import SANDBOX_PROJECT_ENDPOINT
from src.config.foundry_vm_start_binding import build_vm_start_foundry_binding
from src.workflows.incident_resolution.azure_read_tool_authority import (
    build_default_azure_read_tool_authority_registry,
)
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBinding, CapabilityFoundryAgentBindingRegistry,
)
from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
from src.workflows.incident_resolution.vm_start_foundry_binding import VmStartFoundryBinding


DEPLOYMENT_KEY = "FOUNDRY_DEPLOYMENT_JSON"
_PUBLICATION_FIELDS = frozenset((
    "agent_name", "agent_version", "connection_reference", "server_url", "server_label",
))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate deployment field.")
        result[key] = value
    return result


def _object(value, fields, field):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{field} requires exactly its declared fields.")
    return value


def _name(value, field, *, agent=False):
    pattern = r"agent-[a-z0-9]+(?:-[a-z0-9]+)*" if agent else r"[A-Za-z0-9][A-Za-z0-9_-]*"
    if (type(value) is not str or not re.fullmatch(pattern, value)
            or re.search(r"(?:^|[-_])(?:poc|probe)(?:$|[-_])", value, re.I)
            or value.casefold() in {"agent-azure-operations-sbx", "azure-mcp-operations-sbx",
                                    "azure-mcp-operations-server"}):
        raise ValueError(f"{field} requires an exact dedicated non-POC/non-probe name.")
    return value


def _version(value):
    if type(value) is not str or not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("Agent version must be an explicit positive numeric string.")
    return value


def _https(value, field, *, root=False):
    if (type(value) is not str or not value or value != value.strip()
            or any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value):
        raise ValueError(f"{field} requires an exact HTTPS URL.")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.port not in (None, 443) or (root and parsed.path not in ("", "/"))):
        raise ValueError(f"{field} requires an exact HTTPS URL without credentials.")
    if not root and not re.fullmatch(r"/api/projects/[A-Za-z0-9_-]+", parsed.path):
        raise ValueError("project_endpoint requires an explicit Foundry project path.")
    return value


def _publication(value, field):
    value = _object(value, _PUBLICATION_FIELDS, field)
    _name(value["agent_name"], f"{field}.agent_name", agent=True)
    _version(value["agent_version"])
    _name(value["connection_reference"], f"{field}.connection_reference")
    _name(value["server_label"], f"{field}.server_label")
    _https(value["server_url"], f"{field}.server_url", root=True)
    _name(urlsplit(value["server_url"]).hostname.split(".", 1)[0], f"{field}.hostname")
    return value


@dataclass(frozen=True)
class FoundryDeploymentConfiguration:
    project_endpoint: str
    catalog: Mapping[AgentKey, FoundryAgentDefinition]
    read_bindings: CapabilityFoundryAgentBindingRegistry
    write_binding: VmStartFoundryBinding
    read_connection_reference: str
    read_server_url: str
    fingerprint: str


def build_foundry_deployment_configuration(
    environment: Mapping[str, object],
) -> FoundryDeploymentConfiguration | None:
    """Opt-in is complete and atomic; malformed input never selects sandbox defaults."""
    if not isinstance(environment, Mapping):
        raise TypeError("environment must implement Mapping.")
    if DEPLOYMENT_KEY not in environment:
        return None
    conflicting = set(AGENT_VERSION_ENV_VARS.values()) | {"FOUNDRY_CAPABILITY_BINDING_PROFILE"}
    if any(key in conflicting or key.startswith(("FOUNDRY_RG_LIST_", "FOUNDRY_VM_START_"))
           for key in environment):
        raise ValueError("Deployment JSON cannot be mixed with legacy selection/publication overrides.")
    raw = environment[DEPLOYMENT_KEY]
    if type(raw) is not str or not raw or len(raw.encode("utf-8")) > 100_000:
        raise ValueError("FOUNDRY_DEPLOYMENT_JSON must be a bounded JSON document.")
    try:
        document = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid deployment JSON.") from exc
    _object(document, ("schema_version", "project_endpoint", "agents", "read", "write"), "deployment")
    if document["schema_version"] != "1.0":
        raise ValueError("Unsupported deployment schema_version.")
    endpoint = _https(document["project_endpoint"], "project_endpoint")
    if endpoint != environment.get("FOUNDRY_PROJECT_ENDPOINT"):
        raise ValueError("Deployment differs from FOUNDRY_PROJECT_ENDPOINT.")
    agents = _object(document["agents"], {key.value for key in AgentKey}, "agents")
    catalog = {}
    for key in AgentKey:
        definition = _object(agents[key.value], ("name", "version"), key.value)
        catalog[key] = FoundryAgentDefinition(
            key=key, name=_name(definition["name"], key.value, agent=True),
            version=_version(definition["version"]),
        )
    if len({item.name for item in catalog.values()}) != len(catalog):
        raise ValueError("Specialist roles require distinct agent names.")
    read = _publication(document["read"], "read")
    write = _publication(document["write"], "write")
    if read["agent_name"] in {item.name for item in catalog.values()}:
        raise ValueError("The READ agent must be separate from the cognitive and WRITE catalog.")
    for field in ("connection_reference", "server_label"):
        if read[field].casefold() == write[field].casefold():
            raise ValueError(f"READ and WRITE must use distinct {field} values.")
    if urlsplit(read["server_url"]).hostname == urlsplit(write["server_url"]).hostname:
        raise ValueError("READ and WRITE require distinct server hosts.")
    if (endpoint == SANDBOX_PROJECT_ENDPOINT
            and read["agent_name"] == "agent-azure-operations-rg-list-sbx"
            and read["agent_version"] in {"1", "2"}):
        raise ValueError("Historical excluded READ versions remain excluded.")
    write_environment = {
        "FOUNDRY_PROJECT_ENDPOINT": endpoint,
        "FOUNDRY_VM_START_BINDING_PROFILE": "azure-vm-start-isolated-v1",
        **{f"FOUNDRY_VM_START_{key.upper()}": value for key, value in write.items()},
    }
    write_binding = build_vm_start_foundry_binding(write_environment)
    if catalog[AgentKey.AZURE_OPERATIONS] != write_binding.agent_definition:
        raise ValueError("The Azure Operations catalog must pin the dedicated WRITE publication.")
    capability_id = "azure.resource_group.list"
    authority = replace(
        build_default_azure_read_tool_authority_registry().get(capability_id),
        server_label=read["server_label"],
    )
    binding = CapabilityFoundryAgentBinding(
        capability=build_default_capability_registry().get(capability_id),
        read_tool_authority=authority,
        agent_definition=FoundryAgentDefinition(
            key=AgentKey.AZURE_OPERATIONS, name=read["agent_name"], version=read["agent_version"],
        ),
        require_approval="always",
    )
    return FoundryDeploymentConfiguration(
        project_endpoint=endpoint, catalog=MappingProxyType(catalog),
        read_bindings=CapabilityFoundryAgentBindingRegistry(bindings=(binding,)),
        write_binding=write_binding, read_connection_reference=read["connection_reference"],
        read_server_url=read["server_url"],
        fingerprint=hashlib.sha256(json.dumps(
            {"deployment": document,
             "managed_identity_client_id": environment.get("FOUNDRY_MANAGED_IDENTITY_CLIENT_ID")},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest(),
    )
