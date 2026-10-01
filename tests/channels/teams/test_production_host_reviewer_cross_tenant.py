from __future__ import annotations

import importlib
from types import SimpleNamespace


TARGET_MODULE = (
    "src.channels.teams.production_composition"
)

TEAMS_MANAGED_IDENTITY_CLIENT_ID = (
    "7fa09b7a-cc8f-48e5-af88-1600d924c799"
)


async def _communication_runner(
    request,
):
    return request


async def _review_runner(
    request,
):
    return request


def test_cross_tenant_mapping_branch_propagates_review_runner(
    monkeypatch,
):
    """
    F24 regression:

    Cuando authorization_identity_mappings es truthy,
    el composition port debe propagar exactamente el
    mismo review_runner al bootstrap productivo.

    La identidad cross-tenant sólo selecciona el
    resolver de identidad. No puede eliminar el
    Reviewer del pipeline terminal.
    """

    module = importlib.import_module(
        TARGET_MODULE
    )

    environment = {
        "EXPLICIT": "mapping",
    }

    app_settings = SimpleNamespace(
        managed_identity_client_id=(
            TEAMS_MANAGED_IDENTITY_CLIENT_ID
        ),
    )

    sql_settings = object()

    mapping = object()

    host_settings = SimpleNamespace(
        app_settings=app_settings,
        azure_sql_settings=sql_settings,
        authorization_identity_mappings=(
            mapping,
        ),
    )

    observation_settings = object()
    reader = object()
    membership_checker = object()
    operator_identity_resolver = object()
    incident_agents = object()
    bootstrap = object()

    captured = {}

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        lambda actual_environment: (
            host_settings
        ),
    )

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        lambda **kwargs: (
            membership_checker
        ),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        lambda actual_environment: (
            observation_settings
        ),
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        lambda actual_settings: (
            reader
        ),
    )

    def fake_resolver_builder(
        *,
        mappings,
    ):
        captured["mappings"] = mappings

        return operator_identity_resolver

    monkeypatch.setattr(
        module,
        "build_exact_teams_authorization_object_id_resolver",
        fake_resolver_builder,
    )

    def fake_bootstrap_builder(
        actual_app_settings,
        actual_sql_settings,
        *,
        membership_checker,
        azure_vm_power_state_reader,
        communication_runner,
        incident_agents,
        operator_identity_resolver,
        review_runner=None,
    ):
        captured.update(
            {
                "app_settings": actual_app_settings,
                "sql_settings": actual_sql_settings,
                "membership_checker": membership_checker,
                "reader": azure_vm_power_state_reader,
                "communication_runner": communication_runner,
                "incident_agents": incident_agents,
                "operator_identity_resolver": (
                    operator_identity_resolver
                ),
                "review_runner": review_runner,
            }
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        (
            "build_production_teams_hitl_app_"
            "with_communication_and_incident_agents"
        ),
        fake_bootstrap_builder,
    )

    result = (
        module
        .build_production_teams_host_with_communication_and_incident_agents(
            environment,
            communication_runner=(
                _communication_runner
            ),
            review_runner=(
                _review_runner
            ),
            incident_agents=(
                incident_agents
            ),
        )
    )

    assert result is bootstrap

    assert captured["mappings"] == (
        mapping,
    )

    assert (
        captured["operator_identity_resolver"]
        is operator_identity_resolver
    )

    assert (
        captured["communication_runner"]
        is _communication_runner
    )

    assert (
        captured["incident_agents"]
        is incident_agents
    )

    #
    # RED esperado en d39ffa2:
    #
    # La rama authorization_identity_mappings
    # actualmente omite review_runner.
    #
    assert captured["review_runner"] is _review_runner