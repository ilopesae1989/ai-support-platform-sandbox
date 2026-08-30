from microsoft_teams.cards import (
    AdaptiveCard,
)

from src.channels.teams.approval_card import (
    build_teams_approval_card,
)

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
    ResolvedParameter,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)


def create_request(
) -> ApprovalRequest:
    return ApprovalRequest(
        workflow_id=(
            "wf-11111111-1111-4111-"
            "8111-111111111111"
        ),

        approval_id=(
            APPROVAL_ID
        ),

        alert_id=(
            "ALT-AZ-VM-001"
        ),

        correlation_id=(
            "corr-001"
        ),

        conversation_id=(
            "19:conversation-001@thread.v2"
        ),

        procedure_id=(
            "NTTSY-SBX-AZ-VM-002"
        ),

        procedure_version=(
            "1.0"
        ),

        current_step=1,

        step_id="1",

        description=(
            "Arrancar la máquina virtual "
            "autorizada."
        ),

        operation_domain=(
            "azure"
        ),

        operation_kind=(
            OperationKind.WRITE.value
        ),

        operation_action=(
            OperationAction.VM_START.value
        ),

        capability_id=(
            "azure.vm.start"
        ),

        hitl_required=True,

        next_action=(
            "execute_step"
        ),

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),

        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value="sub-001",
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            ),

            ResolvedParameter(
                name="resource_group",
                value="rg-demo",
                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            ),

            ResolvedParameter(
                name="vm_name",
                value="vm-demo",
                source=(
                    "normalized_alert."
                    "vm_name"
                ),
            ),
        ],
    )


def serialize_card(
    card: AdaptiveCard,
) -> dict:
    return card.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )


def test_approval_card_is_real_adaptive_card():
    card = (
        build_teams_approval_card(
            create_request()
        )
    )

    assert isinstance(
        card,
        AdaptiveCard,
    )


def test_card_uses_teams_supported_adaptive_card_version_1_5():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    assert (
        payload["version"]
        == "1.5"
    )

def test_card_contains_governed_snapshot_values():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    serialized = str(
        payload
    )

    required_values = [
        "ALT-AZ-VM-001",
        "NTTSY-SBX-AZ-VM-002",
        "1.0",
        "azure.vm.start",
        "vm_start",
        "sub-001",
        "rg-demo",
        "vm-demo",
        "Arrancar la máquina virtual autorizada.",
    ]

    for value in required_values:
        assert (
            value
            in serialized
        )


def test_card_has_exactly_two_execute_actions():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    actions = []

    def collect(
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            if (
                value.get("type")
                == "Action.Execute"
            ):
                actions.append(
                    value
                )

            for child in value.values():
                collect(
                    child
                )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                collect(
                    child
                )

    collect(
        payload
    )

    assert (
        len(actions)
        == 2
    )


def test_execute_payload_contains_only_minimal_hitl_data():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    execute_actions = []

    def collect(
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            if (
                value.get("type")
                == "Action.Execute"
            ):
                execute_actions.append(
                    value
                )

            for child in value.values():
                collect(
                    child
                )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                collect(
                    child
                )

    collect(
        payload
    )

    assert (
        len(execute_actions)
        == 2
    )

    for action in execute_actions:
        data = (
            action["data"]
        )

        assert set(
            data
        ) == {
            "action",
            "approval_id",
            "decision",
        }

        assert (
            data["action"]
            == "approval_decision"
        )

        assert (
            data["approval_id"]
            == APPROVAL_ID
        )

        assert (
            data["decision"]
            in {
                "approve",
                "reject",
            }
        )


def test_card_never_returns_operational_authority():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    execute_actions = []

    def collect(
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            if (
                value.get("type")
                == "Action.Execute"
            ):
                execute_actions.append(
                    value
                )

            for child in value.values():
                collect(
                    child
                )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                collect(
                    child
                )

    collect(
        payload
    )

    forbidden = {
        "workflow_id",
        "alert_id",
        "procedure_id",
        "procedure_version",
        "step_id",
        "operation_domain",
        "operation_kind",
        "operation_action",
        "capability_id",
        "target_resource",
        "subscription_id",
        "resource_group",
        "vm_name",
        "request_id",
        "checkpoint_id",
        "tenant_id",
        "aad_object_id",
    }

    for action in execute_actions:
        data = action["data"]

        assert (
            forbidden.isdisjoint(
                data
            )
        )


def test_actions_do_not_submit_associated_inputs():
    payload = (
        serialize_card(
            build_teams_approval_card(
                create_request()
            )
        )
    )

    serialized = str(
        payload
    )

    assert (
        "associatedInputs"
        in serialized
    )

    assert (
        "none"
        in serialized.lower()
    )