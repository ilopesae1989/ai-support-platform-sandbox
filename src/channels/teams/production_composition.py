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

from src.channels.teams.authorization_identity_resolver import (
    build_exact_teams_authorization_object_id_resolver,
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

    authorization_identity_mappings = getattr(
        host_settings,
        "authorization_identity_mappings",
        (),
    )

    if authorization_identity_mappings:
        operator_identity_resolver = (
            build_exact_teams_authorization_object_id_resolver(
                mappings=(
                    authorization_identity_mappings
                )
            )
        )

        return build_production_teams_hitl_app(
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            membership_checker=(
                membership_checker
            ),
            azure_vm_power_state_reader=reader,
            operator_identity_resolver=(
                operator_identity_resolver
            ),
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

    authorization_identity_mappings = getattr(
        host_settings,
        "authorization_identity_mappings",
        (),
    )

    if authorization_identity_mappings:
        operator_identity_resolver = (
            build_exact_teams_authorization_object_id_resolver(
                mappings=(
                    authorization_identity_mappings
                )
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
                operator_identity_resolver=(
                    operator_identity_resolver
                ),
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

from src.channels.teams.production_bootstrap import (
    build_production_teams_hitl_app_with_communication_and_incident_agents,
)


def build_production_teams_host_with_communication_and_incident_agents(
    environment,
    *,
    communication_runner: object,
    incident_agents: object,
):
    """
    Propaga dependencias ya compuestas.

    Esta capa permanece agnóstica respecto a
    credenciales y proveedores cognitivos.
    """

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

    if incident_agents is None:
        raise TypeError(
            "incident_agents debe existir."
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

    authorization_identity_mappings = getattr(
        host_settings,
        "authorization_identity_mappings",
        (),
    )

    if authorization_identity_mappings:
        operator_identity_resolver = (
            build_exact_teams_authorization_object_id_resolver(
                mappings=(
                    authorization_identity_mappings
                )
            )
        )

        return (
            build_production_teams_hitl_app_with_communication_and_incident_agents(
                host_settings.app_settings,
                host_settings.azure_sql_settings,
                membership_checker=(
                    membership_checker
                ),
                azure_vm_power_state_reader=reader,
                communication_runner=(
                    communication_runner
                ),
                incident_agents=(
                    incident_agents
                ),
                operator_identity_resolver=(
                    operator_identity_resolver
                ),
            )
        )

    return (
        build_production_teams_hitl_app_with_communication_and_incident_agents(
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            membership_checker=(
                membership_checker
            ),
            azure_vm_power_state_reader=reader,
            communication_runner=(
                communication_runner
            ),
            incident_agents=(
                incident_agents
            ),
        )
    )
