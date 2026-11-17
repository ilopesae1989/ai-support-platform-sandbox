from __future__ import annotations

from src.config.continuation_recovery import parse_continuation_recovery_policy
from src.channels.teams.recovery_composition import attach_continuation_recovery

from src.config.procedure_configuration import ProcedureConfiguration

from src.workflows.incident_resolution.vm_start_foundry_binding import GovernedVmStartRoute, VmStartFoundryBinding

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

    recovery_policy = parse_continuation_recovery_policy(environment)

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

        return attach_continuation_recovery(build_production_teams_hitl_app(
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            membership_checker=(
                membership_checker
            ),
            azure_vm_power_state_reader=reader,
            operator_identity_resolver=(
                operator_identity_resolver
            ),
        ), recovery_policy)

    return attach_continuation_recovery(build_production_teams_hitl_app(
        host_settings.app_settings,
        host_settings.azure_sql_settings,
        membership_checker=(
            membership_checker
        ),
        azure_vm_power_state_reader=reader,
    ), recovery_policy)


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

    recovery_policy = parse_continuation_recovery_policy(environment)

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

        return attach_continuation_recovery((
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
        ), recovery_policy)

    return attach_continuation_recovery((
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
    ), recovery_policy)

from src.channels.teams.production_bootstrap import (
    build_production_teams_hitl_app_with_communication_and_incident_agents,
)


from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingRegistry,
)


def build_production_teams_host_with_communication_and_incident_agents(
    environment,
    *,
    communication_runner: object,
    incident_agents: object,
    review_runner: object | None = None,
    capability_foundry_agent_binding_registry: (
        CapabilityFoundryAgentBindingRegistry | None
    ) = None,
    vm_start_route: GovernedVmStartRoute | None = None,
    attestation_publisher=None,
    vm_start_binding: VmStartFoundryBinding | None = None,
    procedure_configuration: ProcedureConfiguration | None = None,
):
    """
    Propaga dependencias ya compuestas.

    Esta capa permanece agnóstica respecto a
    credenciales y proveedores cognitivos.
    """

    # Only explicit selection crosses this layer; direct legacy calls stay unchanged.
    if vm_start_binding is not None:
        if not isinstance(vm_start_binding, VmStartFoundryBinding):
            raise TypeError("vm_start_binding must be VmStartFoundryBinding.")
        if vm_start_route is not None:
            raise ValueError("Specify vm_start_binding or vm_start_route, never both.")
    selector_options = {}
    if attestation_publisher is not None:
        from src.attestation.governor_outbox import GovernorAttestationPublisher
        if type(attestation_publisher) is not GovernorAttestationPublisher:
            raise TypeError("Explicit governor attestation publisher required")
        selector_options["attestation_publisher"] = attestation_publisher
    if procedure_configuration is not None:
        if not isinstance(procedure_configuration, ProcedureConfiguration):
            raise TypeError("procedure_configuration must be ProcedureConfiguration.")
        selector_options["procedure_configuration"] = procedure_configuration
    if vm_start_binding is not None:
        selector_options["vm_start_binding"] = vm_start_binding
    if vm_start_route is not None:
        if not isinstance(vm_start_route, GovernedVmStartRoute):
            raise TypeError("vm_start_route must be GovernedVmStartRoute.")
        selector_options["vm_start_route"] = vm_start_route
    if capability_foundry_agent_binding_registry is not None:
        if not isinstance(
            capability_foundry_agent_binding_registry,
            CapabilityFoundryAgentBindingRegistry,
        ):
            raise TypeError(
                "capability_foundry_agent_binding_registry debe ser "
                "CapabilityFoundryAgentBindingRegistry."
            )
        selector_options["capability_foundry_agent_binding_registry"] = (
            capability_foundry_agent_binding_registry
        )

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

    if (
        review_runner is not None
        and not callable(
            review_runner
        )
    ):
        raise TypeError(
            "review_runner debe ser callable "
            "cuando se proporciona."
        )


    if incident_agents is None:
        raise TypeError(
            "incident_agents debe existir."
        )

    recovery_policy = parse_continuation_recovery_policy(environment)

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

        return attach_continuation_recovery((
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
                **(
                    {"review_runner": review_runner}
                    if review_runner is not None
                    else {}
                ),
                incident_agents=(
                    incident_agents
                ),
                operator_identity_resolver=(
                    operator_identity_resolver
                ),
                **selector_options,
            )
        ), recovery_policy)

    return attach_continuation_recovery((
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
            **(
                {"review_runner": review_runner}
                if review_runner is not None
                else {}
            ),
            incident_agents=(
                incident_agents
            ),
            **selector_options,
        )
    ), recovery_policy)
