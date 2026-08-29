from datetime import (
    datetime,
    timezone,
)

import pytest

from src.workflows.incident_resolution.alert_models import (
    AlertSource,
    NormalizedAlert,
)


TENANT_ID = (
    "33333333-3333-3333-"
    "3333-333333333333"
)

CONVERSATION_ID = (
    "19:phase18-launcher@thread.v2"
)


def create_alert():
    return NormalizedAlert(
        alert_id="alert-phase18-launcher-001",
        source="azure_monitor",
        source_event_id="monitor-event-001",
        name="VM stopped",
        description="Sandbox VM is stopped.",
        source_severity="Sev2",
        timestamp=datetime(
            2026,
            8,
            23,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        affected_resource=(
            "/subscriptions/sub/"
            "resourceGroups/rg/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),
        resource_type=(
            "Microsoft.Compute/virtualMachines"
        ),
        service="azure-vm",
        environment="sandbox",
        subscription_id="sub",
        resource_group="rg",
        vm_name="vm-demo",
        tenant_id=TENANT_ID,
        correlation_id="corr-phase18-001",
    )


@pytest.mark.asyncio
async def test_launcher_builds_one_workflow_and_calls_host_exactly_once(
    monkeypatch,
):
    import src.channels.teams.incident_launcher as launcher

    alert = create_alert()

    workflow = object()
    checkpoint_storage = object()
    store = object()
    outbound = object()
    host_result = object()

    workflow_factory_calls = []
    host_calls = []

    def workflow_factory():
        workflow_factory_calls.append(
            True
        )

        return workflow

    async def fake_host(
        *,
        workflow,
        alert,
        checkpoint_storage,
        store,
        outbound,
        tenant_id,
        conversation_id,
    ):
        host_calls.append(
            {
                "workflow":
                    workflow,

                "alert":
                    alert,

                "checkpoint_storage":
                    checkpoint_storage,

                "store":
                    store,

                "outbound":
                    outbound,

                "tenant_id":
                    tenant_id,

                "conversation_id":
                    conversation_id,
            }
        )

        return host_result

    monkeypatch.setattr(
        launcher,
        "run_incident_until_teams_approval",
        fake_host,
        raising=False,
    )

    result = await (
        launcher
        .start_teams_incident_from_normalized_alert(
            alert=alert,
            workflow_factory=workflow_factory,
            checkpoint_storage=checkpoint_storage,
            store=store,
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert result is host_result

    assert workflow_factory_calls == [
        True
    ]

    assert host_calls == [
        {
            "workflow":
                workflow,

            "alert":
                alert,

            "checkpoint_storage":
                checkpoint_storage,

            "store":
                store,

            "outbound":
                outbound,

            "tenant_id":
                TENANT_ID,

            "conversation_id":
                CONVERSATION_ID,
        }
    ]


@pytest.mark.asyncio
async def test_launcher_rejects_non_normalized_alert_before_workflow_factory():
    import src.channels.teams.incident_launcher as launcher

    workflow_factory_calls = []

    def workflow_factory():
        workflow_factory_calls.append(
            True
        )

        return object()

    with pytest.raises(
        TypeError,
        match="NormalizedAlert",
    ):
        await (
            launcher
            .start_teams_incident_from_normalized_alert(
                alert={
                    "alert_id":
                        "attacker-controlled"
                },
                workflow_factory=workflow_factory,
                checkpoint_storage=object(),
                store=object(),
                outbound=object(),
                tenant_id=TENANT_ID,
                conversation_id=CONVERSATION_ID,
            )
        )

    assert workflow_factory_calls == []


@pytest.mark.asyncio
async def test_launcher_does_not_derive_destination_from_alert():
    import src.channels.teams.incident_launcher as launcher

    alert = create_alert().model_copy(
        update={
            "tenant_id":
                "tenant-from-alert-must-not-route"
        }
    )

    workflow = object()

    host_calls = []

    async def fake_host(
        **kwargs,
    ):
        host_calls.append(
            kwargs
        )

        return object()

    monkeypatch = pytest.MonkeyPatch()

    try:
        monkeypatch.setattr(
            launcher,
            "run_incident_until_teams_approval",
            fake_host,
            raising=False,
        )

        await (
            launcher
            .start_teams_incident_from_normalized_alert(
                alert=alert,
                workflow_factory=lambda: workflow,
                checkpoint_storage=object(),
                store=object(),
                outbound=object(),
                tenant_id=TENANT_ID,
                conversation_id=CONVERSATION_ID,
            )
        )

    finally:
        monkeypatch.undo()

    assert len(
        host_calls
    ) == 1

    assert (
        host_calls[0]["tenant_id"]
        == TENANT_ID
    )

    assert (
        host_calls[0]["conversation_id"]
        == CONVERSATION_ID
    )

    assert (
        host_calls[0]["tenant_id"]
        != alert.tenant_id
    )
