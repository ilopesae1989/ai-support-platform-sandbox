from __future__ import annotations

import asyncio

from azure.identity import (
    AzureCliCredential,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureSdkVmPowerStateReader,
    AzureVmPowerStateReader,
)

from .bootstrap import (
    TeamsHitlSettings,
    build_teams_hitl_app,
)


def build_local_azure_vm_power_state_reader(
) -> AzureVmPowerStateReader:
    """
    Composition root local de la observación
    read-only post-WRITE.

    AzureCliCredential utiliza la sesión Azure CLI
    del operador durante desarrollo/sandbox.

    No solicita token ni realiza una llamada Azure
    durante la construcción.

    Un host Azure deberá sustituir esta credencial
    por ManagedIdentityCredential.
    """

    credential = AzureCliCredential()

    return AzureSdkVmPowerStateReader(
        credential=credential
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

    azure_vm_power_state_reader = (
        build_local_azure_vm_power_state_reader()
    )

    bootstrap = (
        build_teams_hitl_app(
            settings,
            azure_vm_power_state_reader=(
                azure_vm_power_state_reader
            ),
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