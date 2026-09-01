import inspect
import json

import azure.functions as func
import pytest

from src.functions.azure_monitor_blueprint import (
    build_azure_monitor_blueprint,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)


def _payload():
    return {
        "schemaId": (
            "azureMonitorCommonAlertSchema"
        ),
        "data": {
            "essentials": {
                "alertId": (
                    "/subscriptions/"
                    f"{SUBSCRIPTION_ID}"
                    "/providers/"
                    "Microsoft.AlertsManagement/"
                    "alerts/"
                    "11111111-2222-3333-4444-"
                    "555555555555"
                ),
                "alertRule": (
                    "VM unexpected power state"
                ),
                "severity": "Sev0",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "monitoringService": "Platform",
                "alertTargetIDs": [
                    RESOURCE_ID,
                ],
                "configurationItems": [
                    VM_NAME,
                ],
                "originAlertId": (
                    "origin-blueprint-001"
                ),
                "firedDateTime": (
                    "2026-09-01T05:30:00Z"
                ),
                "resolvedDateTime": None,
                "description": "",
                "essentialsVersion": "1.0",
                "alertContextVersion": "1.0",
            },
            "alertContext": {},
            "customProperties": None,
        },
    }


def _request():
    return func.HttpRequest(
        method="POST",
        url=(
            "https://example.test/"
            "api/azure-monitor-alert"
        ),
        headers={
            "content-type": (
                "application/json"
            ),
        },
        params={},
        route_params={},
        body=json.dumps(
            _payload()
        ).encode(
            "utf-8"
        ),
    )


class RecordingAcceptor:
    def __init__(self):
        self.alerts = []

    async def __call__(
        self,
        alert,
    ):
        self.alerts.append(
            alert
        )


class FailingAcceptor:
    async def __call__(
        self,
        alert,
    ):
        raise RuntimeError(
            "downstream acceptance failed"
        )


def _registered_single_function(
    blueprint,
):
    app = func.FunctionApp()

    app.register_functions(
        blueprint
    )

    functions = app.get_functions()

    assert len(functions) == 1

    return functions[0]


def test_blueprint_requires_callable_acceptor():
    with pytest.raises(
        TypeError,
        match="acceptor",
    ):
        build_azure_monitor_blueprint(
            acceptor=object(),
        )


def test_blueprint_declares_exact_http_contract():
    blueprint = (
        build_azure_monitor_blueprint(
            acceptor=RecordingAcceptor(),
        )
    )

    assert isinstance(
        blueprint,
        func.Blueprint,
    )

    function = (
        _registered_single_function(
            blueprint
        )
    )

    assert (
        function.get_function_name()
        == "azure_monitor_alert_ingress"
    )

    assert function.is_http_function() is True

    function_json = json.loads(
        function.get_function_json()
    )

    bindings = function_json["bindings"]

    trigger = next(
        binding
        for binding in bindings
        if str(
            binding["type"]
        ).casefold() == "httptrigger"
    )

    assert (
        str(
            trigger["authLevel"]
        ).casefold()
        == "function"
    )

    assert (
        trigger["route"]
        == "azure-monitor-alert"
    )

    assert {
        method.upper()
        for method in trigger["methods"]
    } == {
        "POST",
    }

    output = next(
        binding
        for binding in bindings
        if str(
            binding["type"]
        ).casefold() == "http"
    )

    assert (
        str(
            output["direction"]
        ).casefold()
        == "out"
    )


def test_blueprint_registers_into_function_app():
    blueprint = (
        build_azure_monitor_blueprint(
            acceptor=RecordingAcceptor(),
        )
    )

    function = (
        _registered_single_function(
            blueprint
        )
    )

    assert (
        function.get_function_name()
        == "azure_monitor_alert_ingress"
    )


@pytest.mark.asyncio
async def test_handler_returns_202_only_after_acceptance():
    acceptor = RecordingAcceptor()

    blueprint = (
        build_azure_monitor_blueprint(
            acceptor=acceptor,
        )
    )

    function = (
        _registered_single_function(
            blueprint
        )
    )

    handler = (
        function.get_user_function()
    )

    assert inspect.iscoroutinefunction(
        handler
    )

    response = await handler(
        _request()
    )

    assert isinstance(
        response,
        func.HttpResponse,
    )

    assert response.status_code == 202

    assert len(
        acceptor.alerts
    ) == 1

    alert = acceptor.alerts[0]

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert (
        alert.affected_resource
        == RESOURCE_ID
    )


@pytest.mark.asyncio
async def test_downstream_failure_is_not_hidden():
    blueprint = (
        build_azure_monitor_blueprint(
            acceptor=FailingAcceptor(),
        )
    )

    function = (
        _registered_single_function(
            blueprint
        )
    )

    handler = (
        function.get_user_function()
    )

    with pytest.raises(
        RuntimeError,
        match="downstream acceptance failed",
    ):
        await handler(
            _request()
        )