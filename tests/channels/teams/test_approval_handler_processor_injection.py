from types import (
    SimpleNamespace,
)

import pytest

import src.channels.teams.approval_handler as approval_handler


def test_dependencies_default_to_existing_processor():
    dependencies = (
        approval_handler
        .TeamsApprovalHandlerDependencies(
            policy=object(),
            store=object(),
            workflow_factory=lambda: object(),
        )
    )

    assert (
        dependencies.processor
        is approval_handler
        .process_authorized_teams_approval
    )


@pytest.mark.asyncio
async def test_handler_uses_injected_processor_after_authorization(
    monkeypatch,
):
    invocation = object()
    authorized = object()
    workflow = object()
    store = object()

    expected_invocation = invocation
    expected_store = store
    expected_workflow = workflow

    sequence = []

    def fake_build_invocation(
        activity,
    ):
        sequence.append(
            "parse"
        )

        return invocation

    def fake_authorize(
        *,
        invocation,
        policy,
    ):
        sequence.append(
            "authorize"
        )

        assert (
            invocation
            is expected_invocation
        )

        return authorized

    async def injected_processor(
        *,
        invocation,
        store,
        workflow,
    ):
        sequence.append(
            "processor"
        )

        assert (
            invocation
            is authorized
        )

        assert (
            store
            is expected_store
        )

        assert (
            workflow
            is expected_workflow
        )

        return SimpleNamespace(
            approval_evidence=(
                SimpleNamespace(
                    decision=(
                        SimpleNamespace(
                            value="approve"
                        )
                    )
                )
            )
        )

    async def forbidden_default_processor(
        **kwargs,
    ):
        raise AssertionError(
            "El processor global por defecto "
            "no debe ejecutarse cuando existe "
            "processor inyectado."
        )

    def fake_success_response(
        *,
        approved,
    ):
        sequence.append(
            "response"
        )

        assert approved is True

        return "approved-response"

    monkeypatch.setattr(
        approval_handler,
        "build_teams_approval_invocation",
        fake_build_invocation,
    )

    monkeypatch.setattr(
        approval_handler,
        "authorize_teams_approval_invocation",
        fake_authorize,
    )

    monkeypatch.setattr(
        approval_handler,
        "process_authorized_teams_approval",
        forbidden_default_processor,
    )

    monkeypatch.setattr(
        approval_handler,
        "_build_success_response",
        fake_success_response,
    )

    dependencies = (
        approval_handler
        .TeamsApprovalHandlerDependencies(
            policy=object(),
            store=store,
            workflow_factory=lambda: workflow,
            processor=injected_processor,
        )
    )

    ctx = SimpleNamespace(
        activity=object()
    )

    result = await (
        approval_handler
        .handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert (
        result
        == "approved-response"
    )

    assert sequence == [
        "parse",
        "authorize",
        "processor",
        "response",
    ]
