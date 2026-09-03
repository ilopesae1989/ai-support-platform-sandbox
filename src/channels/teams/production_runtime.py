from __future__ import annotations

import asyncio

from src.channels.teams.bootstrap import (
    TeamsHitlBootstrap,
)


async def run_production_teams_host(
    bootstrap,
) -> None:
    if not isinstance(
        bootstrap,
        TeamsHitlBootstrap,
    ):
        raise TypeError(
            "bootstrap debe ser TeamsHitlBootstrap."
        )

    stop_event = asyncio.Event()

    async def run_app() -> None:
        try:
            await bootstrap.app.start()
        finally:
            stop_event.set()

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(
            bootstrap.continuation_worker.run(
                stop_event=stop_event
            )
        )

        task_group.create_task(
            run_app()
        )
