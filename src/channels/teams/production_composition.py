from __future__ import annotations

from collections.abc import Mapping

from src.channels.teams.production_bootstrap import (
    build_production_teams_hitl_app,
)

from src.channels.teams.production_settings import (
    build_production_teams_host_settings,
)

from src.channels.teams.graph_group_membership import (
    build_managed_identity_graph_membership_client,
)

from src.workflows.incident_resolution.azure_vm_observation_reader import (
    build_azure_vm_observation_reader,
)

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    build_azure_vm_observation_settings,
)


def build_production_teams_host(
    environment,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    host_settings = (
        build_production_teams_host_settings(
            environment
        )
    )

    membership_checker = (
        build_managed_identity_graph_membership_client(
            managed_identity_client_id=(
                host_settings
                .app_settings
                .managed_identity_client_id
            )
        )
    )

    observation_settings = (
        build_azure_vm_observation_settings(
            environment
        )
    )

    reader = (
        build_azure_vm_observation_reader(
            observation_settings
        )
    )

    return build_production_teams_hitl_app(
        host_settings.app_settings,
        host_settings.azure_sql_settings,
        membership_checker=(
            membership_checker
        ),
        azure_vm_power_state_reader=reader,
    )


from src.channels.teams.production_bootstrap import (
    build_production_teams_hitl_app_with_communication,
)


def build_production_teams_host_with_communication(
    environment,
    *,
    communication_runner: object,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    if not callable(
        communication_runner
    ):
        raise TypeError(
            "communication_runner debe ser callable."
        )

    host_settings = (
        build_production_teams_host_settings(
            environment
        )
    )

    membership_checker = (
        build_managed_identity_graph_membership_client(
            managed_identity_client_id=(
                host_settings
                .app_settings
                .managed_identity_client_id
            )
        )
    )

    observation_settings = (
        build_azure_vm_observation_settings(
            environment
        )
    )

    reader = (
        build_azure_vm_observation_reader(
            observation_settings
        )
    )

    return (
        build_production_teams_hitl_app_with_communication(
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            membership_checker=(
                membership_checker
            ),
            azure_vm_power_state_reader=reader,
            communication_runner=(
                communication_runner
            ),
        )
    )
