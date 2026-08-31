from __future__ import annotations

from typing import (
    Protocol,
)

from azure.mgmt.compute import (
    ComputeManagementClient,
)


class AzureVmInstanceViewError(
    RuntimeError
):
    """
    Error fail-closed al observar el estado runtime
    de una VM Azure.

    La observación no concede autoridad operacional
    y no permite ejecutar cambios sobre la VM.
    """

    pass


class AzureVmPowerStateReader(
    Protocol
):
    """
    Boundary read-only para obtener exclusivamente
    el PowerState runtime de una VM exacta.
    """

    def read_power_state(
        self,
        *,
        subscription_id: str,
        resource_group: str,
        vm_name: str,
    ) -> str:
        ...


def _require_exact_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


class AzureSdkVmPowerStateReader:
    """
    Implementación read-only mediante Azure Compute SDK.

    Sólo utiliza:

        ComputeManagementClient
            .virtual_machines
            .instance_view(...)

    No utiliza:
    - begin_start;
    - begin_restart;
    - begin_power_off;
    - begin_deallocate;
    - create/update/delete;
    - Azure MCP;
    - Foundry;
    - LLM.

    La credencial se inyecta externamente.

    Desarrollo local:
        AzureCliCredential puede inyectarse
        desde el composition root.

    Producción:
        debe inyectarse la Managed Identity
        correspondiente.

    La clase nunca decide qué VM consultar.
    subscription_id, resource_group y vm_name
    proceden del caller gobernado.
    """

    def __init__(
        self,
        *,
        credential,
    ) -> None:
        get_token = getattr(
            credential,
            "get_token",
            None,
        )

        if not callable(
            get_token
        ):
            raise TypeError(
                "credential debe implementar "
                "TokenCredential.get_token()."
            )

        self._credential = credential

    @staticmethod
    def _status_code(
        status,
    ) -> str | None:
        if status is None:
            return None

        if isinstance(
            status,
            dict,
        ):
            value = status.get(
                "code"
            )
        else:
            value = getattr(
                status,
                "code",
                None,
            )

        if (
            not isinstance(
                value,
                str,
            )
            or not value
        ):
            return None

        return value

    def read_power_state(
        self,
        *,
        subscription_id: str,
        resource_group: str,
        vm_name: str,
    ) -> str:
        subscription_id = (
            _require_exact_string(
                name="subscription_id",
                value=subscription_id,
            )
        )

        resource_group = (
            _require_exact_string(
                name="resource_group",
                value=resource_group,
            )
        )

        vm_name = (
            _require_exact_string(
                name="vm_name",
                value=vm_name,
            )
        )

        client = (
            ComputeManagementClient(
                credential=self._credential,
                subscription_id=(
                    subscription_id
                ),
            )
        )

        try:
            instance_view = (
                client
                .virtual_machines
                .instance_view(
                    resource_group_name=(
                        resource_group
                    ),
                    vm_name=vm_name,
                )
            )

        finally:
            close = getattr(
                client,
                "close",
                None,
            )

            if callable(
                close
            ):
                close()

        statuses = (
            getattr(
                instance_view,
                "statuses",
                None,
            )
            or []
        )

        power_states = [
            code
            for code
            in (
                self._status_code(
                    status
                )
                for status
                in statuses
            )
            if (
                code is not None
                and code.startswith(
                    "PowerState/"
                )
            )
        ]

        if len(
            power_states
        ) != 1:
            raise AzureVmInstanceViewError(
                "Instance View debe contener "
                "exactamente un PowerState/*. "
                f"Encontrados={len(power_states)}."
            )

        return power_states[0]
