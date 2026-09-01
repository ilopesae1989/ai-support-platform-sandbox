import json

import azure.functions as func
import pytest

from src.functions.azure_monitor_http_receiver import (
    AzureMonitorHttpReceiver,
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

RESOURCE_TYPE = (
    "Microsoft.Compute/virtualMachines"
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
                    "origin-alert-001"
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
    body=None,
):
    if body is None:
        body = json.dumps(
            _payload()
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


def test_valid_post_returns_normalized_alert():
    receiver = AzureMonitorHttpReceiver()

    alert = receiver.receive(
        _request()
    )

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert alert.source == "azure_monitor"

    assert (
        alert.affected_resource
        == RESOURCE_ID
    )

    assert (
        alert.subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        alert.resource_group
        == RESOURCE_GROUP
    )

    assert alert.vm_name == VM_NAME


def test_non_post_request_is_rejected():
    receiver = AzureMonitorHttpReceiver()

    with pytest.raises(
        AzureMonitorHttpReceiverError,
        match="POST",
    ):
        receiver.receive(
            _request(
                method="GET",
            )
        )


def test_invalid_json_is_rejected_as_transport_error():
    receiver = AzureMonitorHttpReceiver()

    with pytest.raises(
        AzureMonitorHttpReceiverError,
        match="JSON",
    ):
        receiver.receive(
            _request(
                body=b"{not-json",
            )
        )


def test_source_contract_error_is_not_hidden():
    payload = _payload()

    payload["schemaId"] = (
        "UnsupportedSchema"
    )

    request = _request(
        body=json.dumps(
            payload
        ).encode(
            "utf-8"
        )
    )

    receiver = AzureMonitorHttpReceiver()

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="schemaId",
    ):
        receiver.receive(
            request
        )


def test_receiver_error_is_value_error():
    assert issubclass(
        AzureMonitorHttpReceiverError,
        ValueError,
    )