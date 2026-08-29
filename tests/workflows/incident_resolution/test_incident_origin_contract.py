from __future__ import annotations

import pytest

from pydantic import (
    ValidationError,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.operational_context import (
    build_operational_context,
)


TDD_MARKER = (
    "TDD_PHASE18_SYNTHETIC_INCIDENT_ORIGIN_RED"
)


def create_alert(
    **overrides,
) -> NormalizedAlert:
    values = {
        "alert_id":
            "alert-phase18-origin-test-001",

        "source":
            "azure_monitor",

        "source_event_id":
            "synthetic-phase18-origin-test-001",

        "name":
            "Synthetic Azure VM incident",

        "description":
            (
                "Synthetic incident used to test "
                "the governed provenance boundary."
            ),

        "source_severity":
            "Sev2",

        "affected_resource":
            "vm-icenter-sbx-demo-01",

        "resource_type":
            (
                "Microsoft.Compute/"
                "virtualMachines"
            ),

        "service":
            "Azure Virtual Machines",

        "environment":
            "sandbox",

        "subscription_id":
            (
                "557fdabc-f3b6-4c24-"
                "a9ae-e9e89b5ad172"
            ),

        "resource_group":
            "rg-icenter-sandbox-vm-demo",

        "vm_name":
            "vm-icenter-sbx-demo-01",

        "correlation_id":
            "corr-phase18-origin-test-001",
    }

    values.update(
        overrides
    )

    return NormalizedAlert(
        **values
    )


def test_legacy_alert_defaults_to_observed_origin():
    alert = create_alert()

    assert (
        alert.incident_origin
        == "observed"
    )

    assert (
        alert.model_dump()[
            "incident_origin"
        ]
        == "observed"
    )


def test_synthetic_demo_origin_is_explicit_and_independent_from_source():
    alert = create_alert(
        incident_origin=(
            "synthetic_demo"
        )
    )

    #
    # source sigue describiendo la fuente lógica.
    #
    assert (
        alert.source
        == "azure_monitor"
    )

    #
    # incident_origin describe la procedencia factual.
    #
    assert (
        alert.incident_origin
        == "synthetic_demo"
    )


def test_unknown_incident_origin_fails_closed():
    with pytest.raises(
        ValidationError
    ):
        create_alert(
            incident_origin=(
                "attacker_controlled"
            )
        )


def test_operational_context_preserves_typed_synthetic_origin():
    alert = create_alert(
        incident_origin=(
            "synthetic_demo"
        )
    )

    context = (
        build_operational_context(
            alert
        )
    )

    assert (
        context.incident_origin
        == "synthetic_demo"
    )


def test_raw_attributes_cannot_grant_synthetic_demo_origin():
    alert = create_alert(
        raw_attributes={
            "incident_origin":
                "synthetic_demo",
        }
    )

    context = (
        build_operational_context(
            alert
        )
    )

    #
    # El payload arbitrario de origen no adquiere
    # autoridad operacional.
    #
    assert (
        alert.incident_origin
        == "observed"
    )

    assert (
        context.incident_origin
        == "observed"
    )