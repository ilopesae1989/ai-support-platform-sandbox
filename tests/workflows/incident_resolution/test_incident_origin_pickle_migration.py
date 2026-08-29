from __future__ import annotations

import pytest

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


TDD_MARKER = (
    "TDD_PHASE18_INCIDENT_ORIGIN_PICKLE_MIGRATION_RED"
)


def _create_alert(
    *,
    incident_origin: str = "observed",
    raw_attributes: dict | None = None,
) -> NormalizedAlert:
    return NormalizedAlert(
        alert_id="alert-pickle-origin-test-001",
        source="azure_monitor",
        incident_origin=incident_origin,
        source_event_id="event-pickle-origin-test-001",
        name="Pickle migration test",
        description=(
            "In-memory schema evolution validation."
        ),
        source_severity="Sev3",
        affected_resource="vm-demo",
        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),
        service="Azure Virtual Machines",
        environment="sandbox",
        raw_attributes=(
            raw_attributes
            or {}
        ),
    )


def _copy_state(
    state: dict,
) -> dict:
    copied = dict(
        state
    )

    copied["__dict__"] = dict(
        state.get(
            "__dict__",
            {}
        )
    )

    copied[
        "__pydantic_fields_set__"
    ] = set(
        state.get(
            "__pydantic_fields_set__",
            set(),
        )
    )

    extra = state.get(
        "__pydantic_extra__"
    )

    copied[
        "__pydantic_extra__"
    ] = (
        dict(extra)
        if isinstance(
            extra,
            dict,
        )
        else extra
    )

    private = state.get(
        "__pydantic_private__"
    )

    copied[
        "__pydantic_private__"
    ] = (
        dict(private)
        if isinstance(
            private,
            dict,
        )
        else private
    )

    return copied


def _legacy_state(
    *,
    raw_attributes: dict | None = None,
) -> dict:
    alert = _create_alert(
        raw_attributes=(
            raw_attributes
        )
    )

    state = _copy_state(
        alert.__getstate__()
    )

    state[
        "__dict__"
    ].pop(
        "incident_origin",
        None,
    )

    state[
        "__pydantic_fields_set__"
    ].discard(
        "incident_origin"
    )

    return state


def _rehydrate(
    state: dict,
) -> NormalizedAlert:
    restored = object.__new__(
        NormalizedAlert
    )

    NormalizedAlert.__setstate__(
        restored,
        state,
    )

    return restored


def test_legacy_pickle_missing_origin_migrates_to_observed():
    restored = _rehydrate(
        _legacy_state()
    )

    assert (
        restored.incident_origin
        == "observed"
    )

    assert (
        restored.__dict__[
            "incident_origin"
        ]
        == "observed"
    )

    assert (
        restored.model_dump()[
            "incident_origin"
        ]
        == "observed"
    )

    #
    # El dato migrado representa el default histórico,
    # no un valor explícitamente proporcionado entonces.
    #
    assert (
        "incident_origin"
        not in restored.__pydantic_fields_set__
    )


def test_legacy_raw_attributes_cannot_grant_synthetic_demo_during_rehydration():
    restored = _rehydrate(
        _legacy_state(
            raw_attributes={
                "incident_origin":
                    "synthetic_demo",
            }
        )
    )

    assert (
        restored.incident_origin
        == "observed"
    )

    assert (
        restored.__dict__[
            "incident_origin"
        ]
        == "observed"
    )


def test_new_pickle_preserves_explicit_synthetic_demo():
    original = _create_alert(
        incident_origin=(
            "synthetic_demo"
        )
    )

    restored = _rehydrate(
        _copy_state(
            original.__getstate__()
        )
    )

    assert (
        restored.incident_origin
        == "synthetic_demo"
    )

    assert (
        restored.__dict__[
            "incident_origin"
        ]
        == "synthetic_demo"
    )


def test_observed_pickle_preserves_observed():
    original = _create_alert(
        incident_origin=(
            "observed"
        )
    )

    restored = _rehydrate(
        _copy_state(
            original.__getstate__()
        )
    )

    assert (
        restored.incident_origin
        == "observed"
    )


def test_pickle_with_unknown_physical_origin_fails_closed():
    original = _create_alert()

    state = _copy_state(
        original.__getstate__()
    )

    state[
        "__dict__"
    ][
        "incident_origin"
    ] = "attacker_controlled"

    with pytest.raises(
        ValueError,
        match="incident_origin",
    ):
        _rehydrate(
            state
        )

# ---------------------------------------------------------------------------
# TDD_PHASE18_OPERATIONAL_CONTEXT_PICKLE_MIGRATION_RED
# ---------------------------------------------------------------------------

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
    build_operational_context,
)


def _create_operational_context(
    *,
    incident_origin: str = "observed",
) -> OperationalContext:
    alert = _create_alert(
        incident_origin=incident_origin,
    )

    return build_operational_context(
        alert
    )


def _rehydrate_operational_context(
    state: dict,
) -> OperationalContext:
    restored = object.__new__(
        OperationalContext
    )

    OperationalContext.__setstate__(
        restored,
        state,
    )

    return restored


def test_legacy_operational_context_missing_origin_migrates_to_observed():
    original = _create_operational_context()

    state = _copy_state(
        original.__getstate__()
    )

    state[
        "__dict__"
    ].pop(
        "incident_origin",
        None,
    )

    state[
        "__pydantic_fields_set__"
    ].discard(
        "incident_origin"
    )

    restored = (
        _rehydrate_operational_context(
            state
        )
    )

    assert (
        restored.incident_origin
        == "observed"
    )

    assert (
        restored.__dict__[
            "incident_origin"
        ]
        == "observed"
    )

    assert (
        "incident_origin"
        not in restored.__pydantic_fields_set__
    )


def test_operational_context_pickle_preserves_synthetic_demo():
    original = _create_operational_context(
        incident_origin="synthetic_demo",
    )

    restored = (
        _rehydrate_operational_context(
            _copy_state(
                original.__getstate__()
            )
        )
    )

    assert (
        restored.incident_origin
        == "synthetic_demo"
    )


def test_operational_context_pickle_unknown_origin_fails_closed():
    original = _create_operational_context()

    state = _copy_state(
        original.__getstate__()
    )

    state[
        "__dict__"
    ][
        "incident_origin"
    ] = "attacker_controlled"

    with pytest.raises(
        ValueError,
        match="incident_origin",
    ):
        _rehydrate_operational_context(
            state
        )