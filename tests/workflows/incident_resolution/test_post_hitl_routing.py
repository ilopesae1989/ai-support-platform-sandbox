from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)
from src.workflows.incident_resolution.routing_post_hitl import (
    route_to_azure_operation,
    route_to_blocked_operation,
    route_to_database_operation,
    route_to_itsm_operation,
    route_to_linux_operation,
    route_to_microsoft365_operation,
    route_to_networking_operation,
    route_to_windows_operation,
)


def create_step(
    *,
    domain: str = "azure",
    kind: OperationKind = OperationKind.READ,
    next_action: NextAction = (
        NextAction.EXECUTE_STEP
    ),
    approved: bool = True,
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-001",
        approval_id="apr-post-hitl-routing-001",
        alert_id="ALT-001",
        procedure_id="PROC-001",
        procedure_version="v1.0",
        current_step=1,
        step_id="1",
        operation_domain=domain,
        operation_kind=kind,
        next_action=next_action,
        target_resource="resource-01",
        required_parameters=[],
        approved=approved,
    )


def get_routes(
    step: ApprovedProcedureStep,
) -> dict[str, bool]:
    return {
        "azure":
            route_to_azure_operation(step),

        "database":
            route_to_database_operation(step),

        "itsm":
            route_to_itsm_operation(step),

        "windows":
            route_to_windows_operation(step),

        "linux":
            route_to_linux_operation(step),

        "networking":
            route_to_networking_operation(step),

        "microsoft365":
            route_to_microsoft365_operation(step),

        "blocked":
            route_to_blocked_operation(step),
    }


def assert_single_route(
    routes: dict[str, bool],
    expected: str,
) -> None:
    assert routes[expected] is True

    assert (
        sum(
            1
            for value in routes.values()
            if value
        )
        == 1
    )


def test_approved_azure_routes_only_to_azure():
    routes = get_routes(
        create_step(
            domain="azure",
        )
    )

    assert_single_route(
        routes,
        "azure",
    )


def test_approved_database_routes_only_to_database():
    routes = get_routes(
        create_step(
            domain="database",
        )
    )

    assert_single_route(
        routes,
        "database",
    )


def test_approved_itsm_routes_only_to_itsm():
    routes = get_routes(
        create_step(
            domain="itsm",
        )
    )

    assert_single_route(
        routes,
        "itsm",
    )


def test_approved_windows_routes_only_to_windows():
    routes = get_routes(
        create_step(
            domain="windows",
        )
    )

    assert_single_route(
        routes,
        "windows",
    )


def test_approved_linux_routes_only_to_linux():
    routes = get_routes(
        create_step(
            domain="linux",
        )
    )

    assert_single_route(
        routes,
        "linux",
    )


def test_approved_networking_routes_only_to_networking():
    routes = get_routes(
        create_step(
            domain="networking",
        )
    )

    assert_single_route(
        routes,
        "networking",
    )


def test_approved_microsoft365_routes_only_to_microsoft365():
    routes = get_routes(
        create_step(
            domain="microsoft365",
        )
    )

    assert_single_route(
        routes,
        "microsoft365",
    )


def test_rejected_step_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            approved=False,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_unknown_domain_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            domain="quantum",
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_wait_operation_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            kind=OperationKind.WAIT,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_none_operation_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            kind=OperationKind.NONE,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_continue_next_action_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            next_action=NextAction.CONTINUE,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_resolved_next_action_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            next_action=NextAction.RESOLVED,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_blocked_next_action_routes_only_to_blocked():
    routes = get_routes(
        create_step(
            next_action=NextAction.BLOCKED,
        )
    )

    assert_single_route(
        routes,
        "blocked",
    )


def test_all_supported_domains_are_mutually_exclusive():
    domains = [
        "azure",
        "database",
        "itsm",
        "windows",
        "linux",
        "networking",
        "microsoft365",
    ]

    for domain in domains:
        routes = get_routes(
            create_step(
                domain=domain,
            )
        )

        assert_single_route(
            routes,
            domain,
        )