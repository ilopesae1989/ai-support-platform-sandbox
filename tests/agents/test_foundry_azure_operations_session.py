import pytest


from src.agents.foundry_agents import (
    FoundryAgents,
)


class FakeSession:
    pass


class FakeApprovalRequest:
    def __init__(self) -> None:
        self.decisions = []

    def to_function_approval_response(
        self,
        approved: bool,
    ):
        self.decisions.append(
            approved
        )

        return {
            "approval_response":
                approved
        }


class FakeMessage:
    def __init__(
        self,
        *,
        role,
        contents,
    ) -> None:
        self.role = role
        self.contents = contents


class CapturingFoundryAgent:
    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.kwargs = kwargs

        self.session = (
            FakeSession()
        )

        self.create_session_calls = 0
        self.run_calls = []

        self.responses = [
            object(),
            object(),
        ]

    def create_session(
        self,
        *,
        session_id=None,
    ):
        self.create_session_calls += 1

        assert session_id is None

        return self.session

    async def run(
        self,
        messages=None,
        *,
        stream=False,
        session=None,
        middleware=None,
        tools=None,
        options=None,
        compaction_strategy=None,
        tokenizer=None,
        function_invocation_kwargs=None,
        client_kwargs=None,
    ):
        self.run_calls.append(
            {
                "messages": messages,
                "stream": stream,
                "session": session,
                "options": options,
            }
        )

        return self.responses[
            len(self.run_calls) - 1
        ]


@pytest.mark.asyncio
async def test_begin_azure_operations_creates_one_session(
    monkeypatch,
):
    created_agents = []

    def fake_foundry_agent(
        **kwargs,
    ):
        agent = (
            CapturingFoundryAgent(
                **kwargs
            )
        )

        created_agents.append(
            agent
        )

        return agent

    monkeypatch.setattr(
        (
            "src.agents.foundry_agents."
            "FoundryAgent"
        ),
        fake_foundry_agent,
    )

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    invocation = (
        await agents
        .begin_azure_operations(
            "VM Start gobernado."
        )
    )

    assert len(
        created_agents
    ) == 1

    agent = created_agents[0]

    assert (
        agent.create_session_calls
        == 1
    )

    assert len(
        agent.run_calls
    ) == 1

    first_call = (
        agent.run_calls[0]
    )

    assert (
        first_call["messages"]
        == "VM Start gobernado."
    )

    assert (
        first_call["session"]
        is agent.session
    )

    assert (
        invocation.response
        is agent.responses[0]
    )


@pytest.mark.asyncio
async def test_continue_azure_operations_reuses_exact_agent_and_session(
    monkeypatch,
):
    created_agents = []

    def fake_foundry_agent(
        **kwargs,
    ):
        agent = (
            CapturingFoundryAgent(
                **kwargs
            )
        )

        created_agents.append(
            agent
        )

        return agent

    monkeypatch.setattr(
        (
            "src.agents.foundry_agents."
            "FoundryAgent"
        ),
        fake_foundry_agent,
    )

    monkeypatch.setattr(
        (
            "src.agents.foundry_agents."
            "Message"
        ),
        FakeMessage,
        raising=False,
    )

    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    invocation = (
        await agents
        .begin_azure_operations(
            "VM Start gobernado."
        )
    )

    approval_request = (
        FakeApprovalRequest()
    )

    continued = (
        await agents
        .continue_azure_operations(
            invocation=invocation,
            approval_request=(
                approval_request
            ),
            approved=True,
        )
    )

    assert len(
        created_agents
    ) == 1

    agent = created_agents[0]

    # No se crea una segunda sesión.
    assert (
        agent.create_session_calls
        == 1
    )

    assert len(
        agent.run_calls
    ) == 2

    second_call = (
        agent.run_calls[1]
    )

    # EXACTAMENTE la misma sesión.
    assert (
        second_call["session"]
        is agent.session
    )

    messages = (
        second_call["messages"]
    )

    assert len(
        messages
    ) == 1

    approval_message = (
        messages[0]
    )

    assert (
        approval_message.role
        == "user"
    )

    assert (
        approval_message.contents
        == [
            {
                "approval_response":
                    True
            }
        ]
    )

    # La conversión la realiza el API
    # nativo de Agent Framework.
    assert (
        approval_request.decisions
        == [True]
    )

    assert (
        continued.response
        is agent.responses[1]
    )


@pytest.mark.asyncio
async def test_continue_azure_operations_rejects_invalid_invocation(
    monkeypatch,
):
    agents = FoundryAgents(
        project_endpoint=(
            "https://example.invalid/"
            "api/projects/test"
        )
    )

    approval_request = (
        FakeApprovalRequest()
    )

    with pytest.raises(
        ValueError
    ):
        await agents.continue_azure_operations(
            invocation=object(),
            approval_request=(
                approval_request
            ),
            approved=True,
        )

    # No debe generar siquiera una
    # approval response si el contexto
    # de ejecución es inválido.
    assert (
        approval_request.decisions
        == []
    )
