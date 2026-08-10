from src.agents.audit import (
    AgentInvocationMetadata,
)
from src.agents.catalog import (
    AgentKey,
    FoundryAgentDefinition,
)


def test_invocation_metadata_records_exact_version():
    definition = FoundryAgentDefinition(
        key=AgentKey.PROCEDURE_EXECUTION,
        name="agent-procedure-execution-sbx",
        version="4",
    )

    metadata = (
        AgentInvocationMetadata.from_definition(
            definition
        )
    )

    assert (
        metadata.agent_key
        == AgentKey.PROCEDURE_EXECUTION
    )

    assert (
        metadata.agent_name
        == "agent-procedure-execution-sbx"
    )

    assert metadata.agent_version == "4"

    assert metadata.invoked_at_utc