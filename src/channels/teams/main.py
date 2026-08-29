from __future__ import annotations

import asyncio

from .bootstrap import (
    TeamsHitlSettings,
    build_teams_hitl_app,
)


async def run_teams_hitl_app() -> None:
    """
    Arranca el canal Teams HITL.

    Orden:

        environment
            ↓
        TeamsHitlSettings
            ↓
        governed bootstrap
            ↓
        Teams SDK App
            ↓
        HTTP server

    No introduce autoridad operacional.
    """

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    bootstrap = (
        build_teams_hitl_app(
            settings
        )
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


def main() -> None:
    """
    Entry point síncrono del proceso Teams.

    Microsoft Teams SDK utiliza asyncio para
    el ciclo de vida de App.
    """

    asyncio.run(
        run_teams_hitl_app()
    )


if __name__ == "__main__":
    main()