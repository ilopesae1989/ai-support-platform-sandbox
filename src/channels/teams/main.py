from __future__ import annotations

import asyncio

from azure.identity import (
    AzureCliCredential,
)

from azure.identity.aio import (
    AzureCliCredential as AsyncAzureCliCredential,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureSdkVmPowerStateReader,
    AzureVmPowerStateReader,
)

from .bootstrap import (
    TeamsHitlConfigurationError,
    TeamsHitlSettings,
    build_teams_hitl_app,
)

from .graph_group_membership import (
    MicrosoftGraphGroupMembershipClient,
    UrllibGraphJsonTransport,
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


def build_local_teams_membership_checker(
    *,
    tenant_id: str,
) -> MicrosoftGraphGroupMembershipClient:
    """
    Compone la consulta local de pertenencia al
    grupo HITL usando la sesión Azure CLI.

    El tenant explícito es el del canal Teams,
    donde se evalúa la identidad del operador.
    No se usa el tenant de autenticación del bot.

    La construcción no solicita tokens ni realiza
    llamadas HTTP. La autorización existente
    deniega si Graph no demuestra la pertenencia.
    """

    if (
        not isinstance(tenant_id, str)
        or not tenant_id
        or tenant_id != tenant_id.strip()
    ):
        raise TeamsHitlConfigurationError(
            "tenant_id de Graph debe ser un string "
            "exacto no vacío."
        )

    credential = AsyncAzureCliCredential(
        tenant_id=tenant_id,
    )

    return MicrosoftGraphGroupMembershipClient(
        credential=credential,
        transport=UrllibGraphJsonTransport(),
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

    membership_checker = (
        build_local_teams_membership_checker(
            tenant_id=settings.teams_channel_tenant_id,
        )
    )

    azure_vm_power_state_reader = (
        build_local_azure_vm_power_state_reader()
    )

    bootstrap = (
        build_teams_hitl_app(
            settings,
            membership_checker=membership_checker,
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