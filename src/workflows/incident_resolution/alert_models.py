from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AlertSource = Literal[
    "azure_monitor",
    "new_relic",
    "dynatrace",
    "scom",
    "zabbix",
    "nagios",
    "prtg",
    "elastic",
    "prometheus",
    "email",
    "servicenow",
    "jira",
    "other",
]


class NormalizedAlert(BaseModel):
    """
    Contrato normalizado de entrada al pipeline cognitivo.

    Ningún agente debe depender directamente del formato
    nativo del fabricante que originó la alerta.
    """

    alert_id: str

    source: AlertSource

    source_event_id: str | None = None

    name: str

    description: str

    source_severity: str | None = None

    timestamp: datetime | None = None

    affected_resource: str | None = None

    resource_type: str | None = None

    service: str | None = None

    environment: str | None = None

    subscription_id: str | None = None

    resource_group: str | None = None

    tenant_id: str | None = None

    correlation_id: str | None = None

    raw_attributes: dict[str, Any] = Field(
        default_factory=dict
    )