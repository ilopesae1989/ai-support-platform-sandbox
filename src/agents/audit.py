from dataclasses import dataclass
from datetime import datetime, timezone

from .catalog import (
    AgentKey,
    FoundryAgentDefinition,
)


@dataclass(frozen=True)
class AgentInvocationMetadata:
    """
    Evidencia mínima de qué definición de agente
    fue utilizada en una invocación.

    No contiene prompts.
    No contiene chain-of-thought.
    No contiene secretos.
    """

    agent_key: AgentKey
    agent_name: str
    agent_version: str
    invoked_at_utc: str

    @classmethod
    def from_definition(
        cls,
        definition: FoundryAgentDefinition,
    ) -> "AgentInvocationMetadata":
        return cls(
            agent_key=definition.key,
            agent_name=definition.name,
            agent_version=definition.version,
            invoked_at_utc=(
                datetime.now(timezone.utc)
                .isoformat()
            ),
        )