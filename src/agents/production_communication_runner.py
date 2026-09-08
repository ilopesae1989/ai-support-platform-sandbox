from __future__ import annotations

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.agents.production_credential import (
    build_foundry_production_credential,
)

from src.agents.production_settings import (
    FoundryProductionSettings,
)


def build_foundry_production_communication_runner(
    settings,
):
    if not isinstance(
        settings,
        FoundryProductionSettings,
    ):
        raise TypeError(
            "settings debe ser "
            "FoundryProductionSettings."
        )

    credential = (
        build_foundry_production_credential(
            settings
        )
    )

    agents = FoundryAgents(
        project_endpoint=(
            settings.project_endpoint
        ),
        credential=credential,
    )

    return agents.run_communication