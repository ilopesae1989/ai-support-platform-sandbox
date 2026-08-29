from dataclasses import fields
from pathlib import Path

import pytest

from src.channels.teams.bootstrap import (
    TeamsHitlConfigurationError,
    TeamsHitlSettings,
)


def configure_current_environment(monkeypatch, tmp_path):
    values = {
        "CLIENT_ID": (
            "11111111-1111-1111-1111-111111111111"
        ),
        "CLIENT_SECRET": "test-secret",
        "TENANT_ID": (
            "22222222-2222-2222-2222-222222222222"
        ),
        "TEAMS_CHANNEL_TENANT_ID": (
            "33333333-3333-3333-3333-333333333333"
        ),
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID": (
            "44444444-4444-4444-4444-444444444444"
        ),
        "TEAMS_HITL_PENDING_DB": str(
            tmp_path / "pending.db"
        ),
        "TEAMS_HITL_CHECKPOINT_DIR": str(
            tmp_path / "checkpoints"
        ),
        "TEAMS_CONVERSATION_BINDING_DB": str(
            tmp_path / "conversation-bindings.db"
        ),
    }

    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_declares_operation_dispatch_database_path():
    field_names = {
        field.name
        for field in fields(TeamsHitlSettings)
    }

    assert "operation_dispatch_database_path" in field_names


def test_operation_dispatch_database_is_required_from_environment(
    monkeypatch,
    tmp_path,
):
    configure_current_environment(
        monkeypatch,
        tmp_path,
    )

    monkeypatch.delenv(
        "TEAMS_OPERATION_DISPATCH_DB",
        raising=False,
    )

    with pytest.raises(
        TeamsHitlConfigurationError,
        match="TEAMS_OPERATION_DISPATCH_DB",
    ):
        TeamsHitlSettings.from_environment()


def test_operation_dispatch_database_path_is_loaded_exactly(
    monkeypatch,
    tmp_path,
):
    configure_current_environment(
        monkeypatch,
        tmp_path,
    )

    expected = tmp_path / "operation-dispatch.db"

    monkeypatch.setenv(
        "TEAMS_OPERATION_DISPATCH_DB",
        str(expected),
    )

    settings = TeamsHitlSettings.from_environment()

    assert (
        settings.operation_dispatch_database_path
        == Path(expected)
    )
