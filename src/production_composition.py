from __future__ import annotations

from collections.abc import Mapping
from src.config.procedure_configuration import build_procedure_configuration
from src.config.foundry_deployment import build_foundry_deployment_configuration

from src.agents.production_communication_runner import (
    build_foundry_production_communication_runner,
    build_foundry_production_agents,
)

from src.agents.production_settings import (
    build_foundry_production_settings,
)

from src.agents.vm_start_production_agents import (
    build_vm_start_production_agents,
)

from src.channels.teams.production_composition import (
    build_production_teams_host_with_communication,
    build_production_teams_host_with_communication_and_incident_agents,
)

from src.config.foundry_capability_bindings import (
    build_capability_foundry_agent_binding_registry,
)

from src.config.foundry_vm_start_binding import (
    build_vm_start_foundry_binding,
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

    deployment = build_foundry_deployment_configuration(environment)
    if deployment is not None:
        if capability_foundry_agent_binding_registry is not None:
            raise ValueError("Deployment JSON owns the READ selector; injection cannot override it.")
        capability_foundry_agent_binding_registry = deployment.read_bindings

    # Resolve explicit configuration before constructing provider dependencies.
    # Absence keeps the selector empty; an injected registry retains its identity.
    if capability_foundry_agent_binding_registry is None:
        capability_foundry_agent_binding_registry = (
            build_capability_foundry_agent_binding_registry(environment)
        )
    elif not isinstance(
        capability_foundry_agent_binding_registry,
        CapabilityFoundryAgentBindingRegistry,
    ):
        raise TypeError(
            "capability_foundry_agent_binding_registry debe ser "
            "CapabilityFoundryAgentBindingRegistry."
        )

    # Resolve the explicit WRITE publication before creating providers.
    # Missing opt-in preserves the historical call shape; malformed input stops.
    vm_start_binding = (
        deployment.write_binding if deployment is not None
        else build_vm_start_foundry_binding(environment)
    )
    procedure_configuration = build_procedure_configuration(environment)
    vm_start_options = {}
    from src.config.f27_attestation import build_governor_attestation_publisher
    attestation_publisher = build_governor_attestation_publisher(environment)
    if attestation_publisher is not None:
        vm_start_options["attestation_publisher"] = attestation_publisher
    if procedure_configuration is not None:
        vm_start_options["procedure_configuration"] = procedure_configuration
    if vm_start_binding is not None:
        vm_start_options["vm_start_binding"] = vm_start_binding

    foundry_settings = (
        build_foundry_production_settings(
            environment
        )
    )

    agent_options = (
        {"catalog": deployment.catalog, "deployment_fingerprint": deployment.fingerprint}
        if deployment is not None else {}
    )
    if vm_start_binding is None:
        incident_agents = build_foundry_production_agents(foundry_settings, **agent_options)
    else:
        incident_agents = build_vm_start_production_agents(
            foundry_settings, vm_start_binding=vm_start_binding, **agent_options,
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
            **vm_start_options,
        )
    )
