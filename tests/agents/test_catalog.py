import pytest

from src.agents.catalog import (
    AgentKey,
    build_agent_catalog,
)


def test_catalog_contains_all_agents():
    catalog = build_agent_catalog()

    assert set(catalog.keys()) == {
        AgentKey.CLASSIFICATION,
        AgentKey.KNOWLEDGE,
        AgentKey.ALERT_TRIAGE,
        AgentKey.PROCEDURE_EXECUTION,
        AgentKey.AZURE_OPERATIONS,
        AgentKey.ITSM,
    }


def test_catalog_uses_expected_sandbox_versions(
    monkeypatch,
):
    for variable in [
        "FOUNDRY_AGENT_CLASSIFICATION_VERSION",
        "FOUNDRY_AGENT_KNOWLEDGE_VERSION",
        "FOUNDRY_AGENT_ALERT_TRIAGE_VERSION",
        "FOUNDRY_AGENT_PROCEDURE_EXECUTION_VERSION",
        "FOUNDRY_AGENT_AZURE_OPERATIONS_VERSION",
        "FOUNDRY_AGENT_ITSM_VERSION",
    ]:
        monkeypatch.delenv(
            variable,
            raising=False,
        )

    catalog = build_agent_catalog()

    assert (
        catalog[AgentKey.CLASSIFICATION].name
        == "agent-classification-sbx"
    )
    assert (
        catalog[AgentKey.CLASSIFICATION].version
        == "7"
    )

    assert (
        catalog[AgentKey.KNOWLEDGE].version
        == "8"
    )

    assert (
        catalog[AgentKey.ALERT_TRIAGE].version
        == "10"
    )

    assert (
        catalog[
            AgentKey.PROCEDURE_EXECUTION
        ].version
        == "5"
    )

    assert (
        catalog[
            AgentKey.AZURE_OPERATIONS
        ].version
        == "11"
    )

    assert (
        catalog[AgentKey.ITSM].version
        == "6"
    )


def test_agent_version_can_be_overridden(
    monkeypatch,
):
    monkeypatch.setenv(
        "FOUNDRY_AGENT_PROCEDURE_EXECUTION_VERSION",
        "99",
    )

    catalog = build_agent_catalog()

    definition = catalog[
        AgentKey.PROCEDURE_EXECUTION
    ]

    assert (
        definition.name
        == "agent-procedure-execution-sbx"
    )

    assert definition.version == "99"


def test_empty_override_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "FOUNDRY_AGENT_PROCEDURE_EXECUTION_VERSION",
        "   ",
    )

    with pytest.raises(
        ValueError,
        match="no puede estar vacío",
    ):
        build_agent_catalog()


def test_catalog_is_immutable():
    catalog = build_agent_catalog()

    with pytest.raises(TypeError):
        catalog[
            AgentKey.PROCEDURE_EXECUTION
        ] = None