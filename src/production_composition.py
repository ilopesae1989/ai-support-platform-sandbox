from __future__ import annotations

from collections.abc import Mapping

from src.agents.production_communication_runner import (
    build_foundry_production_communication_runner,
)

from src.agents.production_settings import (
    build_foundry_production_settings,
)

from src.channels.teams.production_composition import (
    build_production_teams_host_with_communication,
)


def build_production_application(
    environment,
):
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    foundry_settings = (
        build_foundry_production_settings(
            environment
        )
    )

    communication_runner = (
        build_foundry_production_communication_runner(
            foundry_settings
        )
    )

    if not callable(
        communication_runner
    ):
        raise TypeError(
            "communication_runner compuesto debe "
            "ser callable."
        )

    return (
        build_production_teams_host_with_communication(
            environment,
            communication_runner=(
                communication_runner
            ),
        )
    )