from copy import deepcopy
from datetime import datetime, timezone

import pytest

from src.ingestion.azure_monitor import (
    AzureMonitorAlertSourceAdapter,
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

TARGET_RESOURCE_TYPE = (
    "Microsoft.Compute/virtualMachines"
)

TARGET_RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)

ALERT_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/providers/Microsoft.AlertsManagement/"
    "alerts/"
    "11111111-2222-3333-4444-555555555555"
)

ORIGIN_ALERT_ID = (
    "origin-alert-vm-power-state-001"
)


def _build_common_alert_payload(
    *,
    monitor_condition="Fired",
    target_ids=None,
):
    if target_ids is None:
        target_ids = [
            TARGET_RESOURCE_ID,
        ]

    return {
        "schemaId": (
            "azureMonitorCommonAlertSchema"
        ),
        "data": {
            "essentials": {
                "alertId": ALERT_ID,
                "alertRule": (
                    "VM unexpected power state"
                ),
                "alertRuleId": (
                    "/subscriptions/"
                    f"{SUBSCRIPTION_ID}"
                    "/resourceGroups/"
                    f"{RESOURCE_GROUP}"
                    "/providers/Microsoft.Insights/"
                    "metricAlerts/"
                    "vm-unexpected-power-state"
                ),
                "severity": "Sev0",
                "signalType": "Metric",
                "monitorCondition": (
                    monitor_condition
                ),
                "monitoringService": "Platform",
                "alertTargetIDs": target_ids,
                "configurationItems": [
                    VM_NAME,
                ],
                "originAlertId": ORIGIN_ALERT_ID,
                "firedDateTime": (
                    "2026-09-01T05:30:00Z"
                ),
                "resolvedDateTime": None,
                "description": (
                    "La máquina virtual no se "
                    "encuentra en el estado esperado."
                ),
                "essentialsVersion": "1.0",
                "alertContextVersion": "1.0",
                "targetResourceGroup": (
                    RESOURCE_GROUP
                ),
                "targetResourceType": (
                    TARGET_RESOURCE_TYPE
                ),
            },
            "alertContext": {
                "properties": None,
                "conditionType": (
                    "SingleResourceMultipleMetricCriteria"
                ),
                "condition": {
                    "windowSize": "PT5M",
                    "allOf": [
                        {
                            "metricName": (
                                "VmAvailabilityMetric"
                            ),
                            "metricNamespace": (
                                TARGET_RESOURCE_TYPE
                            ),
                            "operator": (
                                "LessThan"
                            ),
                            "threshold": "1",
                            "timeAggregation": (
                                "Average"
                            ),
                            "dimensions": [
                                {
                                    "name": (
                                        "ResourceId"
                                    ),
                                    "value": (
                                        TARGET_RESOURCE_ID
                                    ),
                                },
                            ],
                            "metricValue": 0,
                        },
                    ],
                },
            },
            "customProperties": {
                "environment": "sandbox",
                "procedure_hint": (
                    "informational-only"
                ),
            },
        },
    }


def test_common_schema_fired_single_vm_is_normalized():
    payload = _build_common_alert_payload()
    original_payload = deepcopy(payload)

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    alert = adapter.normalize(payload)

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert payload == original_payload

    assert alert.alert_id == ALERT_ID
    assert alert.source == "azure_monitor"
    assert alert.incident_origin == "observed"

    assert (
        alert.source_event_id
        == ORIGIN_ALERT_ID
    )

    assert (
        alert.name
        == "VM unexpected power state"
    )

    assert alert.description == (
        "La máquina virtual no se "
        "encuentra en el estado esperado."
    )

    assert alert.source_severity == "Sev0"

    assert alert.timestamp == datetime(
        2026,
        9,
        1,
        5,
        30,
        0,
        tzinfo=timezone.utc,
    )

    assert (
        alert.affected_resource
        == TARGET_RESOURCE_ID
    )

    assert (
        alert.resource_type
        == TARGET_RESOURCE_TYPE
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

    # No inventar semántica que el Common Alert
    # Schema no aporta autoritativamente.
    assert alert.service is None
    assert alert.environment is None
    assert alert.tenant_id is None
    assert alert.correlation_id is None

    # raw_attributes es informativo.
    # No concede autoridad operacional.
    assert alert.raw_attributes[
        "schemaId"
    ] == "azureMonitorCommonAlertSchema"

    assert alert.raw_attributes[
        "signalType"
    ] == "Metric"

    assert alert.raw_attributes[
        "monitorCondition"
    ] == "Fired"

    assert alert.raw_attributes[
        "monitoringService"
    ] == "Platform"

    assert alert.raw_attributes[
        "alertTargetIDs"
    ] == [
        TARGET_RESOURCE_ID,
    ]

    assert alert.raw_attributes[
        "configurationItems"
    ] == [
        VM_NAME,
    ]

    assert alert.raw_attributes[
        "alertContext"
    ] == payload["data"]["alertContext"]

    assert alert.raw_attributes[
        "customProperties"
    ] == payload["data"][
        "customProperties"
    ]


def test_non_common_schema_is_rejected():
    payload = _build_common_alert_payload()

    payload["schemaId"] = (
        "AzureMonitorMetricAlert"
    )

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="schemaId",
    ):
        adapter.normalize(payload)


def test_resolved_notification_does_not_start_incident():
    payload = _build_common_alert_payload(
        monitor_condition="Resolved",
    )

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="monitorCondition",
    ):
        adapter.normalize(payload)


def test_multiple_alert_targets_are_rejected_fail_closed():
    second_target = (
        "/subscriptions/"
        f"{SUBSCRIPTION_ID}"
        "/resourceGroups/"
        f"{RESOURCE_GROUP}"
        "/providers/Microsoft.Compute/"
        "virtualMachines/"
        "vm-icenter-sbx-demo-02"
    )

    payload = _build_common_alert_payload(
        target_ids=[
            TARGET_RESOURCE_ID,
            second_target,
        ],
    )

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="alertTargetIDs",
    ):
        adapter.normalize(payload)


def test_adapter_error_is_a_value_error():
    assert issubclass(
        AzureMonitorAlertSourceAdapterError,
        ValueError,
    )

def test_unknown_severity_is_rejected_fail_closed():
    payload = _build_common_alert_payload()

    payload["data"]["essentials"][
        "severity"
    ] = "Critical"

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="severity",
    ):
        adapter.normalize(payload)


def test_unknown_signal_type_is_rejected_fail_closed():
    payload = _build_common_alert_payload()

    payload["data"]["essentials"][
        "signalType"
    ] = "SyntheticSignal"

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="signalType",
    ):
        adapter.normalize(payload)


def test_conflicting_target_resource_group_is_rejected_fail_closed():
    payload = _build_common_alert_payload()

    payload["data"]["essentials"][
        "targetResourceGroup"
    ] = "rg-conflicting-target"

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    with pytest.raises(
        AzureMonitorAlertSourceAdapterError,
        match="targetResourceGroup",
    ):
        adapter.normalize(payload)


def test_custom_properties_cannot_override_resource_identity():
    payload = _build_common_alert_payload()

    payload["data"]["customProperties"] = {
        "subscription_id": (
            "00000000-0000-0000-0000-000000000000"
        ),
        "resource_group": "rg-attacker",
        "vm_name": "vm-attacker",
        "environment": "production",
        "capability_id": "azure.vm.delete",
        "procedure_id": "attacker-procedure",
    }

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    alert = adapter.normalize(payload)

    assert (
        alert.subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        alert.resource_group
        == RESOURCE_GROUP
    )

    assert alert.vm_name == VM_NAME

    assert (
        alert.affected_resource
        == TARGET_RESOURCE_ID
    )

    assert alert.environment is None

    assert alert.raw_attributes[
        "customProperties"
    ] == payload["data"][
        "customProperties"
    ]


def test_nested_non_vm_arm_resource_is_normalized_generically():
    nested_resource_type = (
        "Microsoft.Web/sites/slots"
    )

    nested_target = (
        "/subscriptions/"
        f"{SUBSCRIPTION_ID}"
        "/resourceGroups/"
        f"{RESOURCE_GROUP}"
        "/providers/Microsoft.Web/"
        "sites/app-demo-01/"
        "slots/staging"
    )

    payload = _build_common_alert_payload(
        target_ids=[
            nested_target,
        ],
    )

    payload["data"]["essentials"][
        "targetResourceType"
    ] = nested_resource_type

    payload["data"]["essentials"][
        "configurationItems"
    ] = [
        "app-demo-01/staging",
    ]

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    alert = adapter.normalize(payload)

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert (
        alert.affected_resource
        == nested_target
    )

    assert (
        alert.resource_type
        == nested_resource_type
    )

    assert (
        alert.subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        alert.resource_group
        == RESOURCE_GROUP
    )

    assert alert.vm_name is None

def test_official_common_schema_can_derive_target_metadata_from_arm_id():
    payload = _build_common_alert_payload()

    essentials = payload[
        "data"
    ][
        "essentials"
    ]

    # La muestra oficial de Microsoft Common
    # Alert Schema no materializa necesariamente
    # estos dos campos, aunque el ARM ID contiene
    # la identidad estructural completa.
    essentials.pop(
        "targetResourceGroup"
    )

    essentials.pop(
        "targetResourceType"
    )

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    alert = adapter.normalize(
        payload
    )

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert (
        alert.affected_resource
        == TARGET_RESOURCE_ID
    )

    assert (
        alert.subscription_id
        == SUBSCRIPTION_ID
    )

    assert (
        alert.resource_group
        == RESOURCE_GROUP
    )

    assert (
        alert.resource_type
        == TARGET_RESOURCE_TYPE
    )

    assert alert.vm_name == VM_NAME


def test_official_common_schema_allows_empty_description():
    payload = _build_common_alert_payload()

    payload[
        "data"
    ][
        "essentials"
    ][
        "description"
    ] = ""

    adapter = (
        AzureMonitorAlertSourceAdapter()
    )

    alert = adapter.normalize(
        payload
    )

    assert isinstance(
        alert,
        NormalizedAlert,
    )

    assert alert.description == ""