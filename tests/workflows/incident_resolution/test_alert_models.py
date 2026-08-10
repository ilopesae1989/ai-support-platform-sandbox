from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


def test_valid_azure_monitor_alert():
    alert = NormalizedAlert.model_validate(
        {
            "alert_id": "ALT-CPU-001",
            "source": "azure_monitor",
            "source_event_id": "AZMON-12345",
            "name": "CPU Percentage High",
            "description": (
                "La utilización de CPU ha superado "
                "el 90 % durante 15 minutos."
            ),
            "source_severity": "Sev2",
            "timestamp": (
                datetime.now(timezone.utc)
            ),
            "affected_resource": "vm-demo-01",
            "resource_type": (
                "Microsoft.Compute/virtualMachines"
            ),
            "service": "Azure Virtual Machines",
            "environment": "sandbox",
            "subscription_id": (
                "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
            ),
            "resource_group": "rg-demo",
            "raw_attributes": {
                "metric": "Percentage CPU",
                "threshold": 90,
                "window_minutes": 15,
            },
        }
    )

    assert alert.alert_id == "ALT-CPU-001"
    assert alert.source == "azure_monitor"
    assert alert.affected_resource == "vm-demo-01"


def test_valid_scom_alert():
    alert = NormalizedAlert.model_validate(
        {
            "alert_id": "ALT-SQL-AG-001",
            "source": "scom",
            "name": (
                "Availability Group Replica "
                "Not Synchronizing"
            ),
            "description": (
                "La réplica secundaria del AG-PROD "
                "no está sincronizada."
            ),
            "source_severity": "Critical",
            "affected_resource": "SQLPROD01",
            "resource_type": (
                "Microsoft SQL Server "
                "Always On Availability Group"
            ),
        }
    )

    assert alert.source == "scom"
    assert alert.affected_resource == "SQLPROD01"


def test_unknown_source_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedAlert.model_validate(
            {
                "alert_id": "ALT-001",
                "source": "invented_monitor",
                "name": "Test",
                "description": "Test",
            }
        )


def test_raw_attributes_are_optional():
    alert = NormalizedAlert.model_validate(
        {
            "alert_id": "ALT-001",
            "source": "email",
            "name": "Alerta recibida por correo",
            "description": "Incidencia reportada.",
        }
    )

    assert alert.raw_attributes == {}