from __future__ import annotations

import azure.functions as func

from src.functions.azure_monitor_http_ingress import (
    AzureMonitorHttpIngress,
)


def build_azure_monitor_blueprint(
    *,
    acceptor: object,
) -> func.Blueprint:
    """
    Construye exclusivamente el binding HTTP
    Azure Functions para Azure Monitor.

    El acceptor downstream se inyecta desde la
    composicion superior.

    Este modulo no:

    - conoce Teams;
    - construye contexto de canal;
    - ejecuta workflows;
    - selecciona procedimientos;
    - selecciona capabilities;
    - llama Foundry;
    - llama MCP;
    - concede autoridad operacional.
    """

    if not callable(
        acceptor
    ):
        raise TypeError(
            "acceptor debe ser callable."
        )

    ingress = AzureMonitorHttpIngress(
        acceptor=acceptor,
    )

    blueprint = func.Blueprint()

    @blueprint.function_name(
        name="azure_monitor_alert_ingress"
    )
    @blueprint.route(
        route="azure-monitor-alert",
        methods=[
            "POST",
        ],
        auth_level=func.AuthLevel.FUNCTION,
    )
    async def azure_monitor_alert_ingress(
        req: func.HttpRequest,
    ) -> func.HttpResponse:
        await ingress.accept(
            req
        )

        return func.HttpResponse(
            status_code=202
        )

    return blueprint