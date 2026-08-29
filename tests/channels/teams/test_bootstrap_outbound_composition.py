from pathlib import Path

import src.channels.teams.bootstrap as teams_bootstrap

from src.channels.teams.bootstrap import (
    TeamsHitlSettings,
)


def create_settings(tmp_path):
    return TeamsHitlSettings(
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret="test-secret",
        bot_tenant_id="22222222-2222-2222-2222-222222222222",
        teams_channel_tenant_id=(
            "33333333-3333-3333-3333-333333333333"
        ),
        approver_aad_object_id=(
            "44444444-4444-4444-4444-444444444444"
        ),
        pending_database_path=tmp_path / "pending.db",
        checkpoint_path=tmp_path / "checkpoints",
        operation_dispatch_database_path=(
            tmp_path / "operation-dispatch.db"
        ),
        conversation_binding_database_path=(
            tmp_path / "conversation-bindings.db"
        ),
    )


def install_outbound_fake(*, monkeypatch):
    outbound = object()
    calls = []

    def fake_outbound_dependencies(*, app, store):
        calls.append(
            {
                "app": app,
                "store": store,
            }
        )
        return outbound

    monkeypatch.setattr(
        teams_bootstrap,
        "TeamsOutboundDependencies",
        fake_outbound_dependencies,
        raising=False,
    )

    return outbound, calls


def test_bootstrap_builds_outbound_from_exact_app_and_conversation_store(
    monkeypatch,
    tmp_path,
):
    outbound, calls = install_outbound_fake(
        monkeypatch=monkeypatch,
    )

    bootstrap = teams_bootstrap.build_teams_hitl_app(
        create_settings(tmp_path)
    )

    assert calls == [
        {
            "app": bootstrap.app,
            "store": bootstrap.conversation_store,
        }
    ]

    assert calls[0]["app"] is bootstrap.app
    assert calls[0]["store"] is bootstrap.conversation_store


def test_bootstrap_exposes_same_governed_outbound(
    monkeypatch,
    tmp_path,
):
    outbound, calls = install_outbound_fake(
        monkeypatch=monkeypatch,
    )

    bootstrap = teams_bootstrap.build_teams_hitl_app(
        create_settings(tmp_path)
    )

    assert len(calls) == 1
    assert bootstrap.outbound is outbound
