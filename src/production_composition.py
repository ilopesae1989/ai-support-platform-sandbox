from __future__ import annotations

from collections.abc import Mapping

from src.agents.production_communication_runner import (
    build_foundry_production_communication_runner,
    build_foundry_production_agents,
)

from src.agents.production_settings import (
    build_foundry_production_settings,
)

from src.channels.teams.production_composition import (
    build_production_teams_host_with_communication,
    build_production_teams_host_with_communication_and_incident_agents,
)


from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingRegistry,
)


def build_production_application(
    environment,
    *,
    capability_foundry_agent_binding_registry: (
        CapabilityFoundryAgentBindingRegistry | None
    ) = None,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    # Selection is explicit at the application root, including an empty registry.
    # Each composition owns its default; a supplied registry keeps its identity.
    if capability_foundry_agent_binding_registry is None:
        capability_foundry_agent_binding_registry = (
            CapabilityFoundryAgentBindingRegistry(bindings=())
        )
    elif not isinstance(
        capability_foundry_agent_binding_registry,
        CapabilityFoundryAgentBindingRegistry,
    ):
        raise TypeError(
            "capability_foundry_agent_binding_registry debe ser "
            "CapabilityFoundryAgentBindingRegistry."
        )

    foundry_settings = (
        build_foundry_production_settings(
            environment
        )
    )

    incident_agents = (
        build_foundry_production_agents(
            foundry_settings
        )
    )

    communication_runner = getattr(
        incident_agents,
        "run_communication",
        None,
    )

    if not callable(
        communication_runner
    ):
        raise TypeError(
            "incident_agents debe exponer "
            "run_communication callable."
        )

    review_runner = getattr(
        incident_agents,
        "run_review",
        None,
    )

    if not callable(
        review_runner
    ):
        raise TypeError(
            "incident_agents debe exponer "
            "run_review callable."
        )

    return (
        build_production_teams_host_with_communication_and_incident_agents(
            environment,
            communication_runner=(
                communication_runner
            ),
            review_runner=(
                review_runner
            ),
            incident_agents=(
                incident_agents
            ),
            capability_foundry_agent_binding_registry=(
                capability_foundry_agent_binding_registry
            ),
        )
    )
