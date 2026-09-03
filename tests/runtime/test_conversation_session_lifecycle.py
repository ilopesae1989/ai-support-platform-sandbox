from __future__ import annotations

import dataclasses
import importlib
import inspect
import textwrap

import pytest

from agent_framework import (
    AgentSession,
    SessionStore,
)

from src.runtime.conversation_session_identity import (
    ConversationSessionIdentity,
    build_conversation_session_store_id,
)


MODULE_NAME = (
    "src.runtime."
    "conversation_session_lifecycle"
)


IDENTITY = ConversationSessionIdentity(
    tenant_id="tenant-001",
    conversation_id="conversation-001",
    agent_key="communication",
)


EXPECTED_STORE_ID = (
    build_conversation_session_store_id(
        IDENTITY
    )
)


class RecordingSessionStore(
    SessionStore
):
    def __init__(
        self,
        *,
        loaded=None,
        get_error=None,
        set_error=None,
        events=None,
    ):
        self.loaded = loaded
        self.get_error = get_error
        self.set_error = set_error

        self.events = (
            events
            if events is not None
            else []
        )

        self.get_calls = []
        self.set_calls = []
        self.delete_calls = []

    async def get(
        self,
        session_id,
    ):
        self.events.append(
            "get"
        )

        self.get_calls.append(
            session_id
        )

        if self.get_error is not None:
            raise self.get_error

        return self.loaded

    async def set(
        self,
        session_id,
        session,
    ):
        self.events.append(
            "set"
        )

        self.set_calls.append(
            (
                session_id,
                session,
            )
        )

        if self.set_error is not None:
            raise self.set_error

    async def delete(
        self,
        session_id,
    ):
        self.delete_calls.append(
            session_id
        )


class FakeAgent:
    def __init__(
        self,
        *,
        created_session=None,
        create_error=None,
        run_error=None,
        response=None,
        events=None,
    ):
        self.created_session = (
            created_session
        )

        self.create_error = (
            create_error
        )

        self.run_error = (
            run_error
        )

        self.response = (
            response
            if response is not None
            else object()
        )

        self.events = (
            events
            if events is not None
            else []
        )

        self.create_session_calls = 0
        self.run_calls = []

    def create_session(
        self,
    ):
        self.events.append(
            "create"
        )

        self.create_session_calls += 1

        if self.create_error is not None:
            raise self.create_error

        return self.created_session

    async def run(
        self,
        message,
        *,
        session,
    ):
        self.events.append(
            "run"
        )

        self.run_calls.append(
            (
                message,
                session,
            )
        )

        if self.run_error is not None:
            raise self.run_error

        session.state[
            "runtime_marker"
        ] = "after-run"

        return self.response


def _module():
    return importlib.import_module(
        MODULE_NAME
    )


def _runner():
    module = _module()

    runner = getattr(
        module,
        "run_conversation_agent_turn",
        None,
    )

    assert callable(
        runner
    )

    return runner


def _result_type():
    module = _module()

    result_type = getattr(
        module,
        "ConversationAgentTurnResult",
        None,
    )

    assert result_type is not None

    return result_type


def _session(
    *,
    session_id="framework-session-001",
):
    session = AgentSession(
        session_id=session_id
    )

    session.state = {
        "before": True,
    }

    return session


def test_result_contract_is_frozen_and_exact():
    result_type = _result_type()

    assert dataclasses.is_dataclass(
        result_type
    )

    params = getattr(
        result_type,
        "__dataclass_params__",
    )

    assert params.frozen is True

    assert tuple(
        field.name
        for field in dataclasses.fields(
            result_type
        )
    ) == (
        "session_store_id",
        "session",
        "response",
        "created",
    )


def test_runner_has_exact_keyword_only_surface_and_is_async():
    runner = _runner()

    assert inspect.iscoroutinefunction(
        runner
    )

    signature = inspect.signature(
        runner
    )

    assert tuple(
        signature.parameters
    ) == (
        "identity",
        "session_store",
        "agent",
        "message",
    )

    for parameter in (
        signature.parameters.values()
    ):
        assert (
            parameter.kind
            is inspect.Parameter.KEYWORD_ONLY
        )


@pytest.mark.asyncio
async def test_invalid_identity_fails_before_store_or_agent():
    runner = _runner()

    events = []

    store = RecordingSessionStore(
        events=events
    )

    agent = FakeAgent(
        created_session=_session(),
        events=events,
    )

    for invalid in (
        None,
        object(),
        {},
        "identity",
    ):
        with pytest.raises(
            TypeError
        ):
            await runner(
                identity=invalid,
                session_store=store,
                agent=agent,
                message="hello",
            )

    assert events == []
    assert store.get_calls == []
    assert store.set_calls == []
    assert agent.create_session_calls == 0
    assert agent.run_calls == []


@pytest.mark.asyncio
async def test_invalid_message_fails_before_store_or_agent():
    runner = _runner()

    events = []

    store = RecordingSessionStore(
        events=events
    )

    agent = FakeAgent(
        created_session=_session(),
        events=events,
    )

    for invalid in (
        None,
        object(),
        "",
        " ",
        " message",
        "message ",
        "\tmessage",
        "message\n",
    ):
        with pytest.raises(
            (
                TypeError,
                ValueError,
            )
        ):
            await runner(
                identity=IDENTITY,
                session_store=store,
                agent=agent,
                message=invalid,
            )

    assert events == []
    assert store.get_calls == []
    assert store.set_calls == []
    assert agent.create_session_calls == 0
    assert agent.run_calls == []


@pytest.mark.asyncio
async def test_existing_session_is_reused_run_and_persisted_after_success():
    runner = _runner()

    events = []

    existing = _session(
        session_id="existing-session"
    )

    store = RecordingSessionStore(
        loaded=existing,
        events=events,
    )

    agent = FakeAgent(
        created_session=_session(),
        response="response-001",
        events=events,
    )

    result = await runner(
        identity=IDENTITY,
        session_store=store,
        agent=agent,
        message="hello",
    )

    assert events == [
        "get",
        "run",
        "set",
    ]

    assert store.get_calls == [
        EXPECTED_STORE_ID
    ]

    assert agent.create_session_calls == 0

    assert agent.run_calls == [
        (
            "hello",
            existing,
        )
    ]

    assert store.set_calls == [
        (
            EXPECTED_STORE_ID,
            existing,
        )
    ]

    assert existing.state[
        "runtime_marker"
    ] == "after-run"

    assert result.session_store_id == (
        EXPECTED_STORE_ID
    )

    assert result.session is existing
    assert result.response == "response-001"
    assert result.created is False


@pytest.mark.asyncio
async def test_missing_session_is_created_run_and_persisted():
    runner = _runner()

    events = []

    created = _session(
        session_id="created-session"
    )

    store = RecordingSessionStore(
        loaded=None,
        events=events,
    )

    agent = FakeAgent(
        created_session=created,
        response="response-created",
        events=events,
    )

    result = await runner(
        identity=IDENTITY,
        session_store=store,
        agent=agent,
        message="hello",
    )

    assert events == [
        "get",
        "create",
        "run",
        "set",
    ]

    assert store.get_calls == [
        EXPECTED_STORE_ID
    ]

    assert agent.create_session_calls == 1

    assert agent.run_calls == [
        (
            "hello",
            created,
        )
    ]

    assert store.set_calls == [
        (
            EXPECTED_STORE_ID,
            created,
        )
    ]

    assert result.session_store_id == (
        EXPECTED_STORE_ID
    )

    assert result.session is created
    assert result.response == "response-created"
    assert result.created is True


@pytest.mark.asyncio
async def test_restored_value_must_be_exact_agent_session():
    runner = _runner()

    for invalid in (
        object(),
        {},
        "session",
    ):
        events = []

        store = RecordingSessionStore(
            loaded=invalid,
            events=events,
        )

        agent = FakeAgent(
            created_session=_session(),
            events=events,
        )

        with pytest.raises(
            TypeError
        ):
            await runner(
                identity=IDENTITY,
                session_store=store,
                agent=agent,
                message="hello",
            )

        assert events == [
            "get",
        ]

        assert agent.create_session_calls == 0
        assert agent.run_calls == []
        assert store.set_calls == []


@pytest.mark.asyncio
async def test_created_value_must_be_exact_agent_session():
    runner = _runner()

    for invalid in (
        None,
        object(),
        {},
        "session",
    ):
        events = []

        store = RecordingSessionStore(
            loaded=None,
            events=events,
        )

        agent = FakeAgent(
            created_session=invalid,
            events=events,
        )

        with pytest.raises(
            TypeError
        ):
            await runner(
                identity=IDENTITY,
                session_store=store,
                agent=agent,
                message="hello",
            )

        assert events == [
            "get",
            "create",
        ]

        assert agent.create_session_calls == 1
        assert agent.run_calls == []
        assert store.set_calls == []


@pytest.mark.asyncio
async def test_get_failure_propagates_before_create_run_or_set():
    runner = _runner()

    expected_error = RuntimeError(
        "session get failure"
    )

    events = []

    store = RecordingSessionStore(
        get_error=expected_error,
        events=events,
    )

    agent = FakeAgent(
        created_session=_session(),
        events=events,
    )

    with pytest.raises(
        RuntimeError,
        match="session get failure",
    ) as exc_info:
        await runner(
            identity=IDENTITY,
            session_store=store,
            agent=agent,
            message="hello",
        )

    assert exc_info.value is expected_error

    assert events == [
        "get",
    ]

    assert agent.create_session_calls == 0
    assert agent.run_calls == []
    assert store.set_calls == []


@pytest.mark.asyncio
async def test_agent_run_failure_is_not_persisted():
    runner = _runner()

    expected_error = RuntimeError(
        "agent run failure"
    )

    events = []

    existing = _session()

    store = RecordingSessionStore(
        loaded=existing,
        events=events,
    )

    agent = FakeAgent(
        run_error=expected_error,
        events=events,
    )

    with pytest.raises(
        RuntimeError,
        match="agent run failure",
    ) as exc_info:
        await runner(
            identity=IDENTITY,
            session_store=store,
            agent=agent,
            message="hello",
        )

    assert exc_info.value is expected_error

    assert events == [
        "get",
        "run",
    ]

    assert store.set_calls == []


@pytest.mark.asyncio
async def test_set_failure_propagates_only_after_successful_run():
    runner = _runner()

    expected_error = RuntimeError(
        "session set failure"
    )

    events = []

    existing = _session()

    store = RecordingSessionStore(
        loaded=existing,
        set_error=expected_error,
        events=events,
    )

    agent = FakeAgent(
        response="completed",
        events=events,
    )

    with pytest.raises(
        RuntimeError,
        match="session set failure",
    ) as exc_info:
        await runner(
            identity=IDENTITY,
            session_store=store,
            agent=agent,
            message="hello",
        )

    assert exc_info.value is expected_error

    assert events == [
        "get",
        "run",
        "set",
    ]

    assert len(
        agent.run_calls
    ) == 1

    assert len(
        store.set_calls
    ) == 1


@pytest.mark.asyncio
async def test_storage_key_is_owned_only_by_conversation_identity():
    runner = _runner()

    identities = (
        ConversationSessionIdentity(
            tenant_id="tenant-a",
            conversation_id="conversation",
            agent_key="communication",
        ),
        ConversationSessionIdentity(
            tenant_id="tenant-b",
            conversation_id="conversation",
            agent_key="communication",
        ),
        ConversationSessionIdentity(
            tenant_id="tenant-a",
            conversation_id="conversation-b",
            agent_key="communication",
        ),
        ConversationSessionIdentity(
            tenant_id="tenant-a",
            conversation_id="conversation",
            agent_key="knowledge",
        ),
    )

    observed = []

    for identity in identities:
        session = _session()

        store = RecordingSessionStore(
            loaded=session
        )

        agent = FakeAgent()

        result = await runner(
            identity=identity,
            session_store=store,
            agent=agent,
            message="hello",
        )

        expected = (
            build_conversation_session_store_id(
                identity
            )
        )

        assert store.get_calls == [
            expected
        ]

        assert store.set_calls == [
            (
                expected,
                session,
            )
        ]

        assert result.session_store_id == expected

        observed.append(
            expected
        )

    assert len(
        set(
            observed
        )
    ) == 4


def test_lifecycle_has_no_identity_backend_or_service_session_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "conversationsessionidentity",
        "build_conversation_session_store_id",
        "sessionstore",
        "agentsession",
        "session_store.get",
        "session_store.set",
        "create_session",
        "agent.run",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "service_session_id ==",
        "service_session_id !=",
        "tenant_id ==",
        "tenant_id !=",
        "conversation_id ==",
        "conversation_id !=",
        "agent_key ==",
        "agent_key !=",
        "os.environ",
        "os.getenv",
        "mssql",
        "sql",
        "sqlite",
        "cosmos",
        "redis",
        "azure",
        "teams",
        "foundry",
        "mcp",
        "credential",
        "client_secret",
        "password",
        "create table",
        "insert into",
        "update dbo",
        "delete from",
    )

    for fragment in forbidden:
        assert fragment not in lowered
