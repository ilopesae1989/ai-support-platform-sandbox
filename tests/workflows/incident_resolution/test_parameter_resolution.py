import pytest

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.parameter_resolution import (
    resolve_required_parameters,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def create_context() -> OperationalContext:
    return OperationalContext(
        alert_id="ALT-AZ-RG-LIST-001",
        affected_resource=(
            SUBSCRIPTION_ID
        ),
        resource_type="subscription",
        service="Azure Resource Manager",
        environment="sandbox",
        subscription_id=(
            SUBSCRIPTION_ID
        ),
        resource_group=None,
        tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),
        correlation_id=(
            "corr-azure-rg-list-live-001"
        ),
    )


def test_subscription_id_resolves_exactly():
    result = (
        resolve_required_parameters(
            required_parameters=[
                "subscription_id",
            ],
            context=create_context(),
        )
    )

    assert result.complete is True

    assert result.required_parameters == [
        "subscription_id",
    ]

    assert result.missing_parameters == []

    assert len(
        result.resolved_parameters
    ) == 1

    parameter = (
        result.resolved_parameters[0]
    )

    assert (
        parameter.name
        == "subscription_id"
    )

    assert (
        parameter.value
        == SUBSCRIPTION_ID
    )

    assert (
        parameter.source
        == "normalized_alert.subscription_id"
    )


def test_missing_parameter_is_fail_closed():
    result = (
        resolve_required_parameters(
            required_parameters=[
                "resource_group",
            ],
            context=create_context(),
        )
    )

    assert result.complete is False

    assert result.resolved_parameters == []

    assert result.missing_parameters == [
        "resource_group",
    ]


def test_unknown_parameter_is_not_invented():
    result = (
        resolve_required_parameters(
            required_parameters=[
                "unknown_parameter",
            ],
            context=create_context(),
        )
    )

    assert result.complete is False

    assert result.resolved_parameters == []

    assert result.missing_parameters == [
        "unknown_parameter",
    ]


def test_parameter_names_are_not_normalized():
    result = (
        resolve_required_parameters(
            required_parameters=[
                "Subscription_ID",
            ],
            context=create_context(),
        )
    )

    assert result.complete is False

    assert result.resolved_parameters == []

    assert result.missing_parameters == [
        "Subscription_ID",
    ]


def test_multiple_parameters_preserve_order():
    result = (
        resolve_required_parameters(
            required_parameters=[
                "tenant_id",
                "subscription_id",
                "environment",
            ],
            context=create_context(),
        )
    )

    assert result.complete is True

    assert [
        item.name
        for item
        in result.resolved_parameters
    ] == [
        "tenant_id",
        "subscription_id",
        "environment",
    ]


def test_duplicate_parameters_are_rejected():
    with pytest.raises(
        ValueError,
        match="duplicados",
    ):
        resolve_required_parameters(
            required_parameters=[
                "subscription_id",
                "subscription_id",
            ],
            context=create_context(),
        )


def test_no_required_parameters_is_complete():
    result = (
        resolve_required_parameters(
            required_parameters=[],
            context=create_context(),
        )
    )

    assert result.complete is True

    assert result.required_parameters == []

    assert result.resolved_parameters == []

    assert result.missing_parameters == []