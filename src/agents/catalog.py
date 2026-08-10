import os
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class AgentKey(StrEnum):
    CLASSIFICATION = "classification"
    KNOWLEDGE = "knowledge"
    ALERT_TRIAGE = "alert_triage"
    PROCEDURE_EXECUTION = "procedure_execution"
    AZURE_OPERATIONS = "azure_operations"
    ITSM = "itsm"


@dataclass(frozen=True)
class FoundryAgentDefinition:
    """
    Referencia inmutable a una versión concreta de un
    Prompt Agent administrado en Microsoft Foundry.
    """

    key: AgentKey
    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                f"El agente {self.key} no tiene nombre."
            )

        if not self.version.strip():
            raise ValueError(
                f"El agente {self.key} no tiene versión."
            )


#
# Catálogo base de la sandbox.
#
# Este es el ÚNICO lugar del código donde se fijan
# las versiones por defecto.
#
_DEFAULT_AGENT_CATALOG: dict[
    AgentKey,
    FoundryAgentDefinition,
] = {
    AgentKey.CLASSIFICATION: FoundryAgentDefinition(
        key=AgentKey.CLASSIFICATION,
        name="agent-classification-sbx",
        version="7",
    ),
    AgentKey.KNOWLEDGE: FoundryAgentDefinition(
        key=AgentKey.KNOWLEDGE,
        name="agent-knowledge-sbx",
        version="8",
    ),
    AgentKey.ALERT_TRIAGE: FoundryAgentDefinition(
        key=AgentKey.ALERT_TRIAGE,
        name="agent-alert-triage-sbx",
        version="10",
    ),
    AgentKey.PROCEDURE_EXECUTION: FoundryAgentDefinition(
        key=AgentKey.PROCEDURE_EXECUTION,
        name="agent-procedure-execution-sbx",
        version="5",
    ),
    AgentKey.AZURE_OPERATIONS: FoundryAgentDefinition(
        key=AgentKey.AZURE_OPERATIONS,
        name="agent-azure-operations-sbx",
        version="11",
    ),
    AgentKey.ITSM: FoundryAgentDefinition(
        key=AgentKey.ITSM,
        name="agent-itsm-sbx",
        version="6",
    ),
}


AGENT_VERSION_ENV_VARS: Mapping[
    AgentKey,
    str,
] = MappingProxyType(
    {
        AgentKey.CLASSIFICATION:
            "FOUNDRY_AGENT_CLASSIFICATION_VERSION",

        AgentKey.KNOWLEDGE:
            "FOUNDRY_AGENT_KNOWLEDGE_VERSION",

        AgentKey.ALERT_TRIAGE:
            "FOUNDRY_AGENT_ALERT_TRIAGE_VERSION",

        AgentKey.PROCEDURE_EXECUTION:
            "FOUNDRY_AGENT_PROCEDURE_EXECUTION_VERSION",

        AgentKey.AZURE_OPERATIONS:
            "FOUNDRY_AGENT_AZURE_OPERATIONS_VERSION",

        AgentKey.ITSM:
            "FOUNDRY_AGENT_ITSM_VERSION",
    }
)


def build_agent_catalog() -> Mapping[
    AgentKey,
    FoundryAgentDefinition,
]:
    """
    Construye el catálogo efectivo.

    Las versiones definidas mediante variables de entorno
    sustituyen únicamente la versión por defecto.

    Los nombres de los agentes no son configurables aquí:
    forman parte de la arquitectura de la plataforma.
    """

    resolved: dict[
        AgentKey,
        FoundryAgentDefinition,
    ] = {}

    for key, default_definition in (
        _DEFAULT_AGENT_CATALOG.items()
    ):
        env_var = AGENT_VERSION_ENV_VARS[key]

        configured_version = os.environ.get(
            env_var,
            default_definition.version,
        ).strip()

        if not configured_version:
            raise ValueError(
                f"{env_var} no puede estar vacío."
            )

        resolved[key] = FoundryAgentDefinition(
            key=key,
            name=default_definition.name,
            version=configured_version,
        )

    return MappingProxyType(resolved)


def get_agent_definition(
    key: AgentKey,
    catalog: Mapping[
        AgentKey,
        FoundryAgentDefinition,
    ] | None = None,
) -> FoundryAgentDefinition:
    effective_catalog = (
        catalog
        if catalog is not None
        else build_agent_catalog()
    )

    try:
        return effective_catalog[key]
    except KeyError as exc:
        raise ValueError(
            f"Agente no registrado: {key}"
        ) from exc