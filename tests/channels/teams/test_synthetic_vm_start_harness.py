from datetime import (
    datetime,
    timezone,
)

from types import (
    SimpleNamespace,
)

import pytest

import src.channels.teams.synthetic_vm_start_harness as harness


ALERT_ID = (
    "demo-vm-start-alert-001"
)

SOURCE_EVENT_ID = (
    "demo-vm-start-event-001"
)

CORRELATION_ID = (
    "demo-vm-start-correlation-001"
)

TEAMS_TENANT_ID = (
    "33333333-3333-3333-"
    "3333-333333333333"
)

TEAMS_CONVERSATION_ID = (
    "19:synthetic-vm-start@thread.v2"
)


def build_alert(
    *,
    state="PowerState/deallocated",
):
    return (
        harness
        .build_exact_synthetic_vm_start_alert(
            alert_id=ALERT_ID,
            source_event_id=(
                SOURCE_EVENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
            observed_power_state=state,
            timestamp=datetime(
                2026,
                8,
                29,
                10,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )


def test_builder_fixes_exact_governed_demo_vm_target():
    alert = build_alert()

    assert (
        alert.incident_origin
        == "synthetic_demo"
    )

    assert alert.source == "azure_monitor"
    assert alert.environment == "sandbox"

    assert (
        alert.subscription_id
        == harness.DEMO_SUBSCRIPTION_ID
    )

    assert (
        alert.resource_group
        == harness.DEMO_RESOURCE_GROUP
    )

    assert (
        alert.vm_name
        == harness.DEMO_VM_NAME
    )

    assert (
        alert.resource_type
        == harness.DEMO_RESOURCE_TYPE
    )

    assert (
        alert.affected_resource
        == harness.DEMO_RESOURCE_ID
    )


def test_builder_does_not_embed_operational_authority():
    alert = build_alert()

    payload = alert.model_dump(
        mode="python"
    )

    assert alert.tenant_id is None
    assert alert.raw_attributes == {}

    forbidden_fields = (
        "procedure_id",
        "procedure_version",
        "capability_id",
        "operation_action",
        "approval_id",
        "approved",
        "conversation_id",
    )

    for field in forbidden_fields:
        assert field not in payload

    serialized = str(
        payload
    )

    assert (
        "NTTSY-SBX-AZ-VM-DEMO-001"
        not in serialized
    )

    assert (
        "azure.vm.start"
        not in serialized
    )


@pytest.mark.parametrize(
    "state",
    [
        "PowerState/stopped",
        "PowerState/deallocated",
    ],
)
def test_builder_accepts_only_supported_non_running_states(
    state,
):
    alert = build_alert(
        state=state
    )

    assert state in alert.description


def test_builder_rejects_running_or_unknown_state():
    for state in (
        "PowerState/running",
        "stopped",
        "deallocated",
        "",
    ):
        with pytest.raises(
            harness.SyntheticVmStartHarnessError,
            match="observed_power_state",
        ):
            build_alert(
                state=state
            )


@pytest.mark.asyncio
async def test_run_reuses_existing_bootstrap_and_launcher(
    monkeypatch,
):
    workflow = object()
    checkpoint_storage = object()
    store = object()
    outbound = object()
    expected_result = object()

    workflow_factory_calls = []

    def workflow_factory():
        workflow_factory_calls.append(
            True
        )

        return workflow

    bootstrap = SimpleNamespace(
        dependencies=SimpleNamespace(
            workflow_factory=(
                workflow_factory
            )
        ),
        checkpoint_storage=(
            checkpoint_storage
        ),
        store=store,
        outbound=outbound,
    )

    launcher_calls = []

    async def fake_launcher(
        **kwargs,
    ):
        launcher_calls.append(
            kwargs
        )

        return expected_result

    monkeypatch.setattr(
        harness,
        "start_teams_incident_from_normalized_alert",
        fake_launcher,
    )

    result = await (
        harness
        .run_exact_synthetic_vm_start_until_teams_approval(
            bootstrap=bootstrap,
            tenant_id=TEAMS_TENANT_ID,
            conversation_id=(
                TEAMS_CONVERSATION_ID
            ),
            alert_id=ALERT_ID,
            source_event_id=(
                SOURCE_EVENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
            observed_power_state=(
                "PowerState/deallocated"
            ),
        )
    )

    assert result is expected_result

    assert workflow_factory_calls == []

    assert len(
        launcher_calls
    ) == 1

    call = launcher_calls[0]

    assert (
        call["workflow_factory"]
        is workflow_factory
    )

    assert (
        call["checkpoint_storage"]
        is checkpoint_storage
    )

    assert call["store"] is store
    assert call["outbound"] is outbound

    assert (
        call["tenant_id"]
        == TEAMS_TENANT_ID
    )

    assert (
        call["conversation_id"]
        == TEAMS_CONVERSATION_ID
    )

    alert = call["alert"]

    assert alert.tenant_id is None

    assert (
        alert.incident_origin
        == "synthetic_demo"
    )

    assert (
        alert.affected_resource
        == harness.DEMO_RESOURCE_ID
    )


@pytest.mark.asyncio
async def test_run_fails_before_launcher_when_bootstrap_is_incomplete(
    monkeypatch,
):
    launcher_calls = []

    async def fake_launcher(
        **kwargs,
    ):
        launcher_calls.append(
            kwargs
        )

        return object()

    monkeypatch.setattr(
        harness,
        "start_teams_incident_from_normalized_alert",
        fake_launcher,
    )

    bootstrap = SimpleNamespace(
        dependencies=SimpleNamespace(
            workflow_factory=None
        ),
        checkpoint_storage=object(),
        store=object(),
        outbound=object(),
    )

    with pytest.raises(
        harness.SyntheticVmStartHarnessError,
        match="workflow_factory",
    ):
        await (
            harness
            .run_exact_synthetic_vm_start_until_teams_approval(
                bootstrap=bootstrap,
                tenant_id=TEAMS_TENANT_ID,
                conversation_id=(
                    TEAMS_CONVERSATION_ID
                ),
                alert_id=ALERT_ID,
                source_event_id=(
                    SOURCE_EVENT_ID
                ),
                correlation_id=(
                    CORRELATION_ID
                ),
                observed_power_state=(
                    "PowerState/deallocated"
                ),
            )
        )

    assert launcher_calls == []
