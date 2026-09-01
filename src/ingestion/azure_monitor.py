from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


_COMMON_SCHEMA_ID = (
    "azureMonitorCommonAlertSchema"
)

_AZURE_VM_RESOURCE_TYPE = (
    "Microsoft.Compute/virtualMachines"
)

_ALLOWED_SEVERITIES = (
    "Sev0",
    "Sev1",
    "Sev2",
    "Sev3",
    "Sev4",
)

_ALLOWED_SIGNAL_TYPES = (
    "Metric",
    "Log",
    "Activity Log",
    "ActivityLog",
)


class AzureMonitorAlertSourceAdapterError(
    ValueError
):
    """
    El payload Azure Monitor no puede cruzar
    de forma segura la frontera de normalización.

    Este error no concede autoridad operacional.
    """

    pass


def _require_mapping(
    *,
    name: str,
    value: object,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} debe ser un objeto JSON."
        )

    return value


def _require_exact_string(
    *,
    name: str,
    value: object,
    allow_empty: bool = False,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} debe ser string."
        )

    if (
        not value
        and not allow_empty
    ):
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} no puede estar vacío."
        )

    if value != value.strip():
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} no puede requerir normalización."
        )

    return value


def _require_list(
    *,
    name: str,
    value: object,
) -> list[Any]:
    if not isinstance(
        value,
        list,
    ):
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} debe ser una lista."
        )

    return value


def _parse_utc_datetime(
    *,
    name: str,
    value: object,
) -> datetime:
    raw_value = _require_exact_string(
        name=name,
        value=value,
    )

    parse_value = raw_value

    if raw_value.endswith("Z"):
        parse_value = (
            raw_value[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            parse_value
        )
    except ValueError as exc:
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} no contiene una fecha ISO 8601 válida."
        ) from exc

    if parsed.tzinfo is None:
        raise AzureMonitorAlertSourceAdapterError(
            f"{name} debe contener timezone."
        )

    return parsed.astimezone(
        timezone.utc
    )


def _parse_single_arm_target(
    *,
    target_resource_id: object,
    declared_resource_type: object,
) -> tuple[
    str,
    str,
    str,
    str,
    str | None,
]:
    """
    Extrae únicamente hechos estructurales del ARM ID.

    No resuelve autoridad operacional.
    No consulta Azure.
    No hace fuzzy matching.
    """

    target = _require_exact_string(
        name="alertTargetIDs[0]",
        value=target_resource_id,
    )

    resource_type: str | None = None

    if declared_resource_type is not None:
        resource_type = _require_exact_string(
            name="targetResourceType",
            value=declared_resource_type,
        )

    if not target.startswith("/"):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no es un ARM ID absoluto."
        )

    segments = target[1:].split("/")

    if any(
        not segment
        for segment in segments
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] contiene segmentos vacíos."
        )

    if len(segments) < 8:
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no contiene una identidad ARM completa."
        )

    if (
        segments[0].casefold()
        != "subscriptions"
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no contiene subscriptions."
        )

    if (
        segments[2].casefold()
        != "resourcegroups"
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no contiene resourceGroups."
        )

    if (
        segments[4].casefold()
        != "providers"
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no contiene providers."
        )

    subscription_id = (
        _require_exact_string(
            name="subscription_id",
            value=segments[1],
        )
    )

    resource_group = (
        _require_exact_string(
            name="resource_group",
            value=segments[3],
        )
    )

    provider_namespace = (
        _require_exact_string(
            name="resource_provider",
            value=segments[5],
        )
    )

    resource_path_segments = (
        segments[6:]
    )

    if (
        len(resource_path_segments) < 2
        or len(resource_path_segments) % 2 != 0
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "alertTargetIDs[0] no contiene pares "
            "ARM type/name válidos."
        )

    resource_type_segments = (
        resource_path_segments[0::2]
    )

    resource_name_segments = (
        resource_path_segments[1::2]
    )

    for index, segment in enumerate(
        resource_type_segments
    ):
        _require_exact_string(
            name=(
                "resource_type_segment"
                f"[{index}]"
            ),
            value=segment,
        )

    for index, segment in enumerate(
        resource_name_segments
    ):
        _require_exact_string(
            name=(
                "resource_name_segment"
                f"[{index}]"
            ),
            value=segment,
        )

    resource_type_from_id = (
        f"{provider_namespace}/"
        + "/".join(
            resource_type_segments
        )
    )

    if (
        resource_type is not None
        and (
            resource_type_from_id.casefold()
            != resource_type.casefold()
        )
    ):
        raise AzureMonitorAlertSourceAdapterError(
            "targetResourceType no coincide con "
            "alertTargetIDs[0]."
        )

    effective_resource_type = (
        resource_type_from_id
        if resource_type is None
        else resource_type
    )

    vm_name: str | None = None
    normalized_resource_type = (
        effective_resource_type
    )
    normalized_target = target

    if (
        effective_resource_type.casefold()
        == _AZURE_VM_RESOURCE_TYPE.casefold()
    ):
        if len(segments) != 8:
            raise AzureMonitorAlertSourceAdapterError(
                "alertTargetIDs[0] de VM contiene "
                "segmentos ARM inesperados."
            )

        vm_name = (
            resource_name_segments[0]
        )

        normalized_resource_type = (
            _AZURE_VM_RESOURCE_TYPE
        )

        normalized_target = (
            f"/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            "/providers/Microsoft.Compute"
            f"/virtualMachines/{vm_name}"
        )

    return (
        normalized_target,
        normalized_resource_type,
        subscription_id,
        resource_group,
        vm_name,
    )


class AzureMonitorAlertSourceAdapter:
    """
    Convierte Azure Monitor Common Alert Schema
    en el contrato vendor-neutral NormalizedAlert.

    Responsabilidad exclusiva:

        payload Azure Monitor
        ->
        hechos normalizados

    No selecciona procedimiento.
    No selecciona capability.
    No autoriza operaciones.
    No crea HITL.
    No decide MCP tools.
    """

    def normalize(
        self,
        payload: object,
    ) -> NormalizedAlert:
        root = _require_mapping(
            name="payload",
            value=payload,
        )

        schema_id = _require_exact_string(
            name="schemaId",
            value=root.get("schemaId"),
        )

        if schema_id != _COMMON_SCHEMA_ID:
            raise AzureMonitorAlertSourceAdapterError(
                "schemaId no corresponde al "
                "Azure Monitor Common Alert Schema."
            )

        data = _require_mapping(
            name="data",
            value=root.get("data"),
        )

        essentials = _require_mapping(
            name="data.essentials",
            value=data.get("essentials"),
        )

        monitor_condition = (
            _require_exact_string(
                name="monitorCondition",
                value=essentials.get(
                    "monitorCondition"
                ),
            )
        )

        if monitor_condition != "Fired":
            raise AzureMonitorAlertSourceAdapterError(
                "monitorCondition debe ser exactamente "
                "Fired para iniciar una incidencia."
            )

        alert_targets = _require_list(
            name="alertTargetIDs",
            value=essentials.get(
                "alertTargetIDs"
            ),
        )

        if len(alert_targets) != 1:
            raise AzureMonitorAlertSourceAdapterError(
                "alertTargetIDs debe contener "
                "exactamente un target."
            )

        declared_resource_type = (
            essentials.get(
                "targetResourceType"
            )
        )

        (
            affected_resource,
            normalized_resource_type,
            subscription_id,
            resource_group,
            vm_name,
        ) = _parse_single_arm_target(
            target_resource_id=(
                alert_targets[0]
            ),
            declared_resource_type=(
                declared_resource_type
            ),
        )

        declared_target_resource_group = (
            essentials.get(
                "targetResourceGroup"
            )
        )

        if (
            declared_target_resource_group
            is not None
        ):
            declared_target_resource_group = (
                _require_exact_string(
                    name="targetResourceGroup",
                    value=(
                        declared_target_resource_group
                    ),
                )
            )

            if (
                declared_target_resource_group.casefold()
                != resource_group.casefold()
            ):
                raise (
                    AzureMonitorAlertSourceAdapterError(
                        "targetResourceGroup no coincide "
                        "con alertTargetIDs[0]."
                    )
                )

        alert_id = _require_exact_string(
            name="alertId",
            value=essentials.get(
                "alertId"
            ),
        )

        source_event_id = (
            _require_exact_string(
                name="originAlertId",
                value=essentials.get(
                    "originAlertId"
                ),
            )
        )

        alert_rule = _require_exact_string(
            name="alertRule",
            value=essentials.get(
                "alertRule"
            ),
        )

        description = (
            _require_exact_string(
                name="description",
                value=essentials.get(
                    "description"
                ),
                allow_empty=True,
            )
        )

        severity = _require_exact_string(
            name="severity",
            value=essentials.get(
                "severity"
            ),
        )

        if severity not in _ALLOWED_SEVERITIES:
            raise AzureMonitorAlertSourceAdapterError(
                "severity no pertenece al contrato "
                "Azure Monitor Common Alert Schema."
            )

        signal_type = (
            _require_exact_string(
                name="signalType",
                value=essentials.get(
                    "signalType"
                ),
            )
        )

        if (
            signal_type
            not in _ALLOWED_SIGNAL_TYPES
        ):
            raise AzureMonitorAlertSourceAdapterError(
                "signalType no pertenece al contrato "
                "Azure Monitor Common Alert Schema."
            )

        monitoring_service = (
            _require_exact_string(
                name="monitoringService",
                value=essentials.get(
                    "monitoringService"
                ),
            )
        )

        fired_datetime = (
            _parse_utc_datetime(
                name="firedDateTime",
                value=essentials.get(
                    "firedDateTime"
                ),
            )
        )

        configuration_items = (
            essentials.get(
                "configurationItems"
            )
        )

        if configuration_items is not None:
            _require_list(
                name="configurationItems",
                value=configuration_items,
            )

        alert_context = data.get(
            "alertContext"
        )

        if alert_context is not None:
            _require_mapping(
                name="alertContext",
                value=alert_context,
            )

        custom_properties = data.get(
            "customProperties"
        )

        if custom_properties is not None:
            _require_mapping(
                name="customProperties",
                value=custom_properties,
            )

        raw_attributes = {
            "schemaId": schema_id,
            "signalType": signal_type,
            "monitorCondition": (
                monitor_condition
            ),
            "monitoringService": (
                monitoring_service
            ),
            "alertTargetIDs": deepcopy(
                alert_targets
            ),
            "configurationItems": deepcopy(
                configuration_items
            ),
            "alertContext": deepcopy(
                alert_context
            ),
            "customProperties": deepcopy(
                custom_properties
            ),
        }

        try:
            return NormalizedAlert(
                alert_id=alert_id,
                source="azure_monitor",
                incident_origin="observed",
                source_event_id=(
                    source_event_id
                ),
                name=alert_rule,
                description=description,
                source_severity=severity,
                timestamp=fired_datetime,
                affected_resource=(
                    affected_resource
                ),
                resource_type=(
                    normalized_resource_type
                ),
                service=None,
                environment=None,
                subscription_id=(
                    subscription_id
                ),
                resource_group=(
                    resource_group
                ),
                vm_name=vm_name,
                tenant_id=None,
                correlation_id=None,
                raw_attributes=(
                    raw_attributes
                ),
            )
        except ValidationError as exc:
            raise AzureMonitorAlertSourceAdapterError(
                "NormalizedAlert rechazó los hechos "
                "extraídos de Azure Monitor."
            ) from exc