from __future__ import annotations

import importlib
import inspect
import json
import textwrap

import pytest

from agent_framework import (
    AgentSession,
)


TARGET_MODULE = (
    "src.runtime.agent_session_snapshot"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _session():
    session = AgentSession(
        session_id="session-001",
        service_session_id=(
            "service-conversation-001"
        ),
    )

    session.state = {
        "turn": 3,
        "profile": {
            "name": "Alice",
            "locale": "es-ES",
        },
        "flags": [
            "a",
            "b",
        ],
    }

    return session


def test_codec_has_exact_surface():
    module = _module()

    error_type = getattr(
        module,
        "AgentSessionSnapshotError",
        None,
    )

    assert error_type is not None

    assert issubclass(
        error_type,
        ValueError,
    )

    encoder = getattr(
        module,
        "encode_agent_session_snapshot",
        None,
    )

    decoder = getattr(
        module,
        "decode_agent_session_snapshot",
        None,
    )

    assert callable(
        encoder
    )

    assert callable(
        decoder
    )

    assert tuple(
        inspect.signature(
            encoder
        ).parameters
    ) == (
        "session",
    )

    assert tuple(
        inspect.signature(
            decoder
        ).parameters
    ) == (
        "payload",
    )


def test_encoder_requires_exact_agent_session():
    module = _module()

    class DerivedSession(
        AgentSession
    ):
        pass

    invalid = (
        None,
        object(),
        {},
        "session",
        DerivedSession(),
    )

    for value in invalid:
        with pytest.raises(
            TypeError
        ):
            module.encode_agent_session_snapshot(
                value
            )


def test_encoder_persists_complete_canonical_snapshot():
    module = _module()

    session = _session()

    expected_dict = (
        session.to_dict()
    )

    payload = (
        module
        .encode_agent_session_snapshot(
            session
        )
    )

    assert isinstance(
        payload,
        str,
    )

    assert payload == json.dumps(
        expected_dict,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    decoded_json = json.loads(
        payload
    )

    assert decoded_json == expected_dict

    assert set(
        decoded_json
    ) == {
        "type",
        "session_id",
        "service_session_id",
        "state",
    }


def test_encoder_fails_closed_for_non_json_snapshot_state():
    module = _module()

    session = AgentSession(
        session_id="session-invalid"
    )

    session.state = {
        "unsupported": object(),
    }

    with pytest.raises(
        module.AgentSessionSnapshotError
    ):
        module.encode_agent_session_snapshot(
            session
        )


def test_decoder_requires_exact_non_empty_payload():
    module = _module()

    invalid = (
        None,
        object(),
        b"{}",
        "",
        " ",
        " {}",
        "{} ",
        "\t{}",
        "{}\n",
    )

    for value in invalid:
        with pytest.raises(
            (
                TypeError,
                module.AgentSessionSnapshotError,
            )
        ):
            module.decode_agent_session_snapshot(
                value
            )


def test_decoder_fails_closed_for_invalid_snapshot_schema():
    module = _module()

    invalid_payloads = (
        "{",
        "[]",
        "{}",
        '{"type":"other","session_id":"s","state":{}}',
        '{"type":"session","state":{}}',
        '{"type":"session","session_id":"","state":{}}',
        '{"type":"session","session_id":"s","state":[]}',
    )

    for payload in invalid_payloads:
        with pytest.raises(
            module.AgentSessionSnapshotError
        ):
            module.decode_agent_session_snapshot(
                payload
            )


def test_roundtrip_preserves_session_and_returns_independent_copy():
    module = _module()

    original = _session()

    payload = (
        module
        .encode_agent_session_snapshot(
            original
        )
    )

    restored = (
        module
        .decode_agent_session_snapshot(
            payload
        )
    )

    assert type(
        restored
    ) is AgentSession

    assert restored is not original

    assert (
        restored.session_id
        == original.session_id
    )

    assert (
        restored.service_session_id
        == original.service_session_id
    )

    assert (
        restored.state
        == original.state
    )

    restored.state[
        "profile"
    ][
        "name"
    ] = "Bob"

    assert original.state[
        "profile"
    ][
        "name"
    ] == "Alice"


def test_service_session_id_is_data_not_authorization_logic():
    module = _module()

    session = AgentSession(
        session_id="session-service"
    )

    session.service_session_id = (
        "opaque-service-id"
    )

    session.state = {}

    payload = (
        module
        .encode_agent_session_snapshot(
            session
        )
    )

    restored = (
        module
        .decode_agent_session_snapshot(
            payload
        )
    )

    assert (
        restored.service_session_id
        == "opaque-service-id"
    )


def test_codec_has_no_storage_network_or_runtime_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "agentsession",
        ".to_dict()",
        "agentsession.from_dict",
        "json.dumps",
        "json.loads",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "sessionstore",
        "filesessionstore",
        "os.environ",
        "os.getenv",
        "open(",
        "pathlib",
        "mssql",
        "sqlite",
        "cosmos",
        "redis",
        "azure",
        "teams",
        "foundry",
        "mcp",
        "get_token",
        "connect(",
        "asyncio",
        "service_session_id ==",
        "service_session_id !=",
    )

    for fragment in forbidden:
        assert fragment not in lowered
