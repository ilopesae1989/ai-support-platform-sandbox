from __future__ import annotations

import azure.functions as func

from src.ingestion.azure_monitor import (
    AzureMonitorAlertSourceAdapter,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


class AzureMonitorHttpReceiverError(
    ValueError
):
    """
    Error de frontera de transporte HTTP.

    No representa un error del contrato
    Azure Monitor Common Alert Schema.
    """

    pass


class AzureMonitorHttpReceiver:
    """
    Frontera HTTP para Azure Monitor.

    Responsabilidad:

        HttpRequest
        ->
        JSON
        ->
        AzureMonitorAlertSourceAdapter
        ->
        NormalizedAlert

    No conoce:

    - Teams;
    - workflow;
    - procedimiento;
    - capability;
    - HITL;
    - Foundry;
    - MCP;
    - autoridad operacional.
    """

    def __init__(
        self,
        *,
        adapter: (
            AzureMonitorAlertSourceAdapter
            | None
        ) = None,
    ) -> None:
        if adapter is None:
            adapter = (
                AzureMonitorAlertSourceAdapter()
            )

        self._adapter = adapter

    def receive(
        self,
        request: func.HttpRequest,
    ) -> NormalizedAlert:
        if not isinstance(
            request,
            func.HttpRequest,
        ):
            raise TypeError(
                "request debe ser "
                "azure.functions.HttpRequest."
            )

        method = request.method

        if method != "POST":
            raise AzureMonitorHttpReceiverError(
                "El receiver acepta "
                "exclusivamente HTTP POST."
            )

        try:
            payload = request.get_json()
        except ValueError as exc:
            raise AzureMonitorHttpReceiverError(
                "El body HTTP no contiene "
                "JSON valido."
            ) from exc

        return self._adapter.normalize(
            payload
        )