import json

import azure.functions as func
import pytest

from src.functions.azure_monitor_http_ingress import (
    AzureMonitorHttpIngress,
)
from src.functions.azure_monitor_http_receiver import (
    AzureMonitorHttpReceiverError,
)
from src.ingestion.azure_monitor import (
    AzureMonitorAlertSourceAdapterError,
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
                    "origin-alert-handoff-001"
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


def _request(
    *,
    method="POST",
    payload=None,
    body=None,
):
    if body is None:
        if payload is None:
            payload = _payload()

        body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

    return func.HttpRequest(
        method=method,
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
        body=body,
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
    def __init__(self):
        self.alerts = []

    async def __call__(
        self,
        alert,
    ):
        self.alerts.append(
            alert
        )

        raise RuntimeError(
            "downstream acceptance failed"
        )


@pytest.mark.asyncio
async def test_valid_request_is_accepted_exactly_once():
    acceptor = RecordingAcceptor()

    ingress = AzureMonitorHttpIngress(
        acceptor=acceptor,
    )

    result = await ingress.accept(
        _request()
    )

    assert isinstance(
        result,
        NormalizedAlert,
    )

    assert len(
        acceptor.alerts
    ) == 1

    assert (
        acceptor.alerts[0]
        is result
    )

    assert (
        result.affected_resource
        == RESOURCE_ID
    )


@pytest.mark.asyncio
async def test_transport_error_does_not_call_acceptor():
    acceptor = RecordingAcceptor()

    ingress = AzureMonitorHttpIngress(
        acceptor=acceptor,
    )

    with pytest.raises(
        AzureMonitorHttpReceiverError,
        match="JSON",
    ):
        await ingress.accept(
            _request(
                body=b"{not-json",
            )
        )

    assert acceptor.alerts == []


@pytest.mark.asyncio
async def test_source_contract_error_does_not_call_acceptor():
    payload = _payload()

    payload["schemaId"] = (
        "UnsupportedSchema"
    )

    acceptor = RecordingAcceptor()

    ingress = AzureMonitorHttpIngress(
        acceptor=acceptor,
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="schemaId",
    ):
        await ingress.accept(
            _request(
                payload=payload,
            )
        )

    assert acceptor.alerts == []


@pytest.mark.asyncio
async def test_downstream_failure_is_not_hidden():
    acceptor = FailingAcceptor()

    ingress = AzureMonitorHttpIngress(
        acceptor=acceptor,
    )

    with pytest.raises(
        RuntimeError,
        match="downstream acceptance failed",
    ):
        await ingress.accept(
            _request()
        )

    assert len(
        acceptor.alerts
    ) == 1


def test_acceptor_must_be_callable():
    with pytest.raises(
        TypeError,
        match="acceptor",
    ):
        AzureMonitorHttpIngress(
            acceptor=object(),
        )