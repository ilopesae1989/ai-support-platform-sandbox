from __future__ import annotations

import inspect

import pytest

import src.channels.teams.bootstrap as teams_bootstrap

from tests.channels.teams.test_bootstrap_outbound_composition import (
    create_settings,
)


class FakeMembershipChecker:
    async def is_transitive_member(
        self,
        *,
        user_object_id,
        group_object_id,
    ):
        raise AssertionError(
            "membership no debe ejecutarse "
            "durante bootstrap."
        )


def test_build_teams_hitl_app_accepts_optional_keyword_only_communication_runner():
    signature = inspect.signature(
        teams_bootstrap.build_teams_hitl_app
    )

    assert (
        "communication_runner"
        in signature.parameters
    )

    parameter = signature.parameters[
        "communication_runner"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert parameter.default is None


@pytest.mark.asyncio
async def test_bootstrap_forwards_exact_runner_only_to_terminal_presenter(
    monkeypatch,
    tmp_path,
):
    captured = {}

    async def communication_runner(
        request,
    ):
        return object()

    async def fake_presenter(
        *,
        invocation,
        processed,
        outbound,
        communication_runner,
    ):
        captured["invocation"] = invocation
        captured["processed"] = processed
        captured["outbound"] = outbound
        captured["communication_runner"] = (
            communication_runner
        )

        return "presented"

    monkeypatch.setattr(
        teams_bootstrap,
        "notify_teams_incident_terminal_result",
        fake_presenter,
        raising=False,
    )

    bootstrap = (
        teams_bootstrap.build_teams_hitl_app(
            create_settings(tmp_path),
            membership_checker=(
                FakeMembershipChecker()
            ),
            communication_runner=(
                communication_runner
            ),
        )
    )

    terminal_notifier = (
        bootstrap
        .continuation_worker
        ._dependencies
        .terminal_notifier
    )

    invocation = object()
    processed = object()

    result = await terminal_notifier(
        invocation=invocation,
        processed=processed,
    )

    assert result == "presented"

    assert captured["invocation"] is invocation
    assert captured["processed"] is processed

    assert captured["outbound"] is (
        bootstrap.outbound
    )

    assert (
        captured["communication_runner"]
        is communication_runner
    )


@pytest.mark.asyncio
async def test_default_none_is_forwarded_to_preserve_deterministic_path(
    monkeypatch,
    tmp_path,
):
    captured = {}

    async def fake_presenter(
        *,
        invocation,
        processed,
        outbound,
        communication_runner,
    ):
        captured["communication_runner"] = (
            communication_runner
        )

        return "presented"

    monkeypatch.setattr(
        teams_bootstrap,
        "notify_teams_incident_terminal_result",
        fake_presenter,
        raising=False,
    )

    bootstrap = (
        teams_bootstrap.build_teams_hitl_app(
            create_settings(tmp_path),
            membership_checker=(
                FakeMembershipChecker()
            ),
        )
    )

    terminal_notifier = (
        bootstrap
        .continuation_worker
        ._dependencies
        .terminal_notifier
    )

    result = await terminal_notifier(
        invocation=object(),
        processed=object(),
    )

    assert result == "presented"

    assert (
        captured["communication_runner"]
        is None
    )


def test_bootstrap_communication_boundary_is_foundry_agnostic():
    source = inspect.getsource(
        teams_bootstrap.build_teams_hitl_app
    ).casefold()

    assert "communication_runner" in source

    forbidden = {
        "foundryagents",
        "run_communication",
        "agentkey",
        "communicationagentadapter",
        "foundry_project_endpoint",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
    }

    for value in forbidden:
        assert value.casefold() not in source