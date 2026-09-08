from __future__ import annotations

import asyncio
import os

from src.channels.teams.production_runtime import (
    run_production_teams_host,
)

from src.production_composition import (
    build_production_application,
)


def main() -> None:
    environment = dict(
        os.environ
    )

    bootstrap = (
        build_production_application(
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