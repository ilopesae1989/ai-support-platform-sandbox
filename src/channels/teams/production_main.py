from __future__ import annotations

import asyncio
import os

from src.channels.teams.production_composition import (
    build_production_teams_host,
)

from src.channels.teams.production_runtime import (
    run_production_teams_host,
)


def main() -> None:
    environment = dict(os.environ)

    bootstrap = (
        build_production_teams_host(
            environment
        )
    )

    asyncio.run(
        run_production_teams_host(
            bootstrap
        )
    )


if __name__ == "__main__":
    main()
