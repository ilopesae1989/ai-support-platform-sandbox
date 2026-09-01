from __future__ import annotations

import azure.functions as func

from src.functions.azure_monitor_http_receiver import (
    AzureMonitorHttpReceiver,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


class AzureMonitorHttpIngress:
    """
    Une la frontera HTTP ya validada con un
    consumidor downstream inyectado.

    Flujo:

        HttpRequest
        ->
        AzureMonitorHttpReceiver
        ->
        NormalizedAlert
        ->
        acceptor

    No:

    - oculta errores de transporte;
    - oculta errores del source adapter;
    - oculta errores downstream;
    - conoce Teams;
    - ejecuta workflows;
    - conoce Foundry;
    - conoce MCP;
    - concede autoridad operacional.
    """

    def __init__(
        self,
        *,
        acceptor: object,
        receiver: (
            AzureMonitorHttpReceiver
            | None
        ) = None,
    ) -> None:
        if not callable(
            acceptor
        ):
            raise TypeError(
                "acceptor debe ser callable."
            )

        if receiver is None:
            receiver = (
                AzureMonitorHttpReceiver()
            )

        self._acceptor = acceptor
        self._receiver = receiver

    async def accept(
        self,
        request: func.HttpRequest,
    ) -> NormalizedAlert:
        alert = self._receiver.receive(
            request
        )

        await self._acceptor(
            alert
        )

        return alert