from __future__ import annotations

import asyncio
import importlib
import inspect
import json

import pytest

from src.agents.catalog import (
    AGENT_VERSION_ENV_VARS,
    AgentKey,
    build_agent_catalog,
)
from src.agents.foundry_agents import FoundryAgents
from src.agents.production_settings import FoundryProductionSettings
from src.communication.contracts import (
    CommunicationRequest,
    CommunicationResult,
)
from src.review.contracts import (
    REQUIRED_REVIEW_CRITERIA,
    REVIEW_CRITERIA_VERSION,
    ReviewRequest,
    ReviewResult,
)
from src.review.policy import (
    build_review_request,
    review_request_sha256,
)


MISSING = "F24_REVIEWER_FOUNDRY_PRODUCT_BINDING_MISSING"
PROJECT_ENDPOINT = (
    "https://aif-example.services.ai.azure.com/"
    "api/projects/project-example"
)
USER_ASSIGNED_CLIENT_ID = (
    "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
)


def _integration():
    production = importlib.import_module(
        "src.agents.production_communication_runner"
    )

    reviewer_key = getattr(
        AgentKey,
        "REVIEWER",
        None,
    )

    run_review = getattr(
        FoundryAgents,
        "run_review",
        None,
    )

    factory = getattr(
        production,
        "build_foundry_production_review_runner",
        None,
    )

    if (
        reviewer_key is None
        or not callable(run_review)
        or not callable(factory)
    ):
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return production, reviewer_key, run_review, factory



@pytest.fixture
def run_async(request):
    provided = getattr(
        request.config,
        "_f24_unit_async_runner",
        None,
    )

    if provided is not None:
        yield provided.run
        return

    with asyncio.Runner(
        loop_factory=asyncio.SelectorEventLoop
    ) as runner:
        yield runner.run


def _settings():
    return FoundryProductionSettings(
        project_endpoint=PROJECT_ENDPOINT,
        managed_identity_client_id=(
            USER_ASSIGNED_CLIENT_ID
        ),
    )


def _review_request() -> ReviewRequest:
    context = CommunicationRequest(
        event_type="resolved",
        alert_id="ALERT-REVIEW-INTEGRATION-001",
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-review-integration",
        technical_summary=(
            "A governed post-operation observation "
            "reports the service healthy."
        ),
        procedure_id="PROC-REVIEW-INTEGRATION-001",
        procedure_name="Synthetic recovery procedure",
        status_summary=(
            "The governed runtime reports "
            "the incident as resolved."
        ),
        escalation_required=False,
        escalation_team=None,
    )

    candidate = CommunicationResult(
        headline="Incident resolved",
        summary="The incident has been resolved.",
        details=[
            "Validation succeeded.",
        ],
    )

    return build_review_request(
        review_id="review-product-integration-001",
        context=context,
        candidate=candidate,
    )


def _result_payload(
    request: ReviewRequest,
) -> dict:
    return {
        "review_id": request.review_id,
        "request_sha256": review_request_sha256(
            request
        ),
        "criteria_version": REVIEW_CRITERIA_VERSION,
        "findings": [
            {
                "criterion": criterion,
                "outcome": "pass",
                "reason": (
                    "Synthetic finding bound to "
                    "the supplied candidate."
                ),
                "evidence_refs": [
                    "/candidate/summary",
                ],
            }
            for criterion in REQUIRED_REVIEW_CRITERIA
        ],
    }


class FakeResponse:
    def __init__(
        self,
        text,
    ) -> None:
        self.text = text


class CapturingFoundryAgent:
    instances = []
    response_text = None

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.kwargs = kwargs
        self.calls = []

        type(self).instances.append(
            self
        )

    async def run(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )

        return FakeResponse(
            type(self).response_text
        )


def test_reviewer_agent_key_is_explicit_and_stable():
    _, reviewer_key, _, _ = _integration()

    assert reviewer_key.value == "reviewer"


def test_catalog_registers_reviewer_v3_by_default(
    monkeypatch,
):
    _, reviewer_key, _, _ = _integration()

    monkeypatch.delenv(
        "FOUNDRY_AGENT_REVIEWER_VERSION",
        raising=False,
    )

    definition = build_agent_catalog()[
        reviewer_key
    ]

    assert definition.name == "agent-reviewer-sbx"
    assert definition.version == "3"


def test_catalog_exposes_reviewer_version_environment_variable():
    _, reviewer_key, _, _ = _integration()

    assert (
        AGENT_VERSION_ENV_VARS[
            reviewer_key
        ]
        == "FOUNDRY_AGENT_REVIEWER_VERSION"
    )


def test_catalog_allows_reviewer_version_override(
    monkeypatch,
):
    _, reviewer_key, _, _ = _integration()

    monkeypatch.setenv(
        "FOUNDRY_AGENT_REVIEWER_VERSION",
        "17",
    )

    assert (
        build_agent_catalog()[
            reviewer_key
        ].version
        == "17"
    )


def test_catalog_rejects_empty_reviewer_version(
    monkeypatch,
):
    _integration()

    monkeypatch.setenv(
        "FOUNDRY_AGENT_REVIEWER_VERSION",
        "   ",
    )

    with pytest.raises(
        ValueError,
        match="no puede estar vacío",
    ):
        build_agent_catalog()


def test_run_review_has_exact_async_surface():
    _, _, run_review, _ = _integration()

    assert inspect.iscoroutinefunction(
        run_review
    )

    assert tuple(
        inspect.signature(
            run_review
        ).parameters
    ) == (
        "self",
        "request",
    )


def test_run_review_rejects_wrong_request_before_agent_creation(
    monkeypatch,
    run_async,
):
    _integration()

    creation_calls = []

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        lambda **kwargs: (
            creation_calls.append(
                kwargs
            )
        ),
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=object(),
    )

    with pytest.raises(
        TypeError,
    ):
        run_async(
            agents.run_review(
                object()
            )
        )

    assert creation_calls == []


def test_run_review_returns_validated_review_result(
    monkeypatch,
    run_async,
):
    _integration()

    request = _review_request()

    CapturingFoundryAgent.instances = []
    CapturingFoundryAgent.response_text = (
        json.dumps(
            _result_payload(
                request
            )
        )
    )

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        CapturingFoundryAgent,
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=object(),
    )

    result = run_async(
        agents.run_review(
            request
        )
    )

    assert type(result) is ReviewResult
    assert result.review_id == request.review_id
    assert (
        result.request_sha256
        == review_request_sha256(
            request
        )
    )


def test_run_review_uses_reviewer_v3_as_single_stateless_call(
    monkeypatch,
    run_async,
):
    _integration()

    request = _review_request()

    CapturingFoundryAgent.instances = []
    CapturingFoundryAgent.response_text = (
        json.dumps(
            _result_payload(
                request
            )
        )
    )

    monkeypatch.setattr(
        "src.agents.foundry_agents.FoundryAgent",
        CapturingFoundryAgent,
    )

    agents = FoundryAgents(
        project_endpoint=PROJECT_ENDPOINT,
        credential=object(),
    )

    run_async(
        agents.run_review(
            request
        )
    )

    assert len(
        CapturingFoundryAgent.instances
    ) == 1

    agent = (
        CapturingFoundryAgent
        .instances[0]
    )

    assert (
        agent.kwargs["agent_name"]
        == "agent-reviewer-sbx"
    )

    assert (
        agent.kwargs["agent_version"]
        == "3"
    )

    assert (
        agent.kwargs.get(
            "default_options"
        )
        is None
    )

    assert "tools" not in agent.kwargs

    assert len(agent.calls) == 1

    call = agent.calls[0]

    assert call["kwargs"] == {}
    assert len(call["args"]) == 1

    sent = json.loads(
        call["args"][0]
    )

    assert set(sent) == {
        "request",
        "request_sha256",
    }

    assert (
        sent["request"]
        == request.model_dump(
            mode="json"
        )
    )

    assert (
        sent["request_sha256"]
        == review_request_sha256(
            request
        )
    )


def test_run_review_reuses_review_agent_adapter_boundary():
    _integration()

    source = inspect.getsource(
        FoundryAgents.run_review
    )

    assert "ReviewAgentAdapter" in source

    forbidden = {
        "create_session",
        "agentsession",
        "session=",
        "chatoptions",
        "tools=",
        "mcp",
        "tenant_id",
        "conversation_id",
        "approval_id",
        "capability_id",
        "resolved_parameters",
        "operation_action",
        "target_resource",
        "assess_review",
    }

    lowered = source.casefold()

    for value in forbidden:
        assert value.casefold() not in lowered


def test_production_review_runner_factory_has_exact_sync_surface():
    _, _, _, factory = _integration()

    assert not inspect.iscoroutinefunction(
        factory
    )

    assert tuple(
        inspect.signature(
            factory
        ).parameters
    ) == (
        "settings",
    )


def test_production_review_runner_rejects_wrong_settings_before_composition(
    monkeypatch,
):
    production, _, _, factory = _integration()

    credential_calls = []

    monkeypatch.setattr(
        production,
        "build_foundry_production_credential",
        lambda settings: (
            credential_calls.append(
                settings
            )
        ),
    )

    for invalid in (
        None,
        object(),
        {},
        "production",
        USER_ASSIGNED_CLIENT_ID,
    ):
        with pytest.raises(
            TypeError,
        ):
            factory(
                invalid
            )

    assert credential_calls == []


def test_production_review_runner_returns_exact_run_review_callable(
    monkeypatch,
):
    production, _, _, factory = _integration()

    expected_runner = object()

    class FakeFoundryAgents:
        def __init__(
            self,
            **kwargs,
        ):
            self.run_review = expected_runner

    monkeypatch.setattr(
        production,
        "build_foundry_production_credential",
        lambda settings: object(),
    )

    monkeypatch.setattr(
        production,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    assert (
        factory(
            _settings()
        )
        is expected_runner
    )


def test_production_review_runner_uses_exact_production_dependencies(
    monkeypatch,
):
    production, _, _, factory = _integration()

    credential = object()
    construction_calls = []

    class FakeFoundryAgents:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            construction_calls.append(
                (
                    args,
                    kwargs,
                )
            )

            self.run_review = object()

    monkeypatch.setattr(
        production,
        "build_foundry_production_credential",
        lambda settings: credential,
    )

    monkeypatch.setattr(
        production,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    factory(
        _settings()
    )

    assert construction_calls == [
        (
            (),
            {
                "project_endpoint": (
                    PROJECT_ENDPOINT
                ),
                "credential": credential,
                "allow_preview": True,
            },
        )
    ]


def test_production_review_runner_does_not_invoke_token_or_agent_during_composition(
    monkeypatch,
):
    production, _, _, factory = _integration()

    calls = []

    class FakeCredential:
        def get_token(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "No token during composition."
            )

    async def forbidden_runner(
        request,
    ):
        calls.append(
            request
        )

        raise AssertionError(
            "No review invocation during composition."
        )

    class FakeFoundryAgents:
        def __init__(
            self,
            **kwargs,
        ):
            self.run_review = forbidden_runner

    monkeypatch.setattr(
        production,
        "build_foundry_production_credential",
        lambda settings: FakeCredential(),
    )

    monkeypatch.setattr(
        production,
        "FoundryAgents",
        FakeFoundryAgents,
    )

    result = factory(
        _settings()
    )

    assert callable(result)
    assert calls == []


def test_production_review_composition_has_no_channel_session_tool_or_operational_authority():
    production, _, _, _ = _integration()

    source = inspect.getsource(
        production
    ).casefold()

    required = {
        "build_foundry_production_review_runner",
        "run_review",
        "foundryproductionsettings",
        "build_foundry_production_credential",
        "foundryagents",
    }

    for value in required:
        assert value in source

    forbidden = {
        "get_token(",
        "await ",
        "asyncio.run",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "send_teams_message",
        "conversation_id",
        "approval_id",
        "capability_id",
        "resolved_parameters",
        "operation_action",
        "target_resource",
        ".run_review(",
    }

    for value in forbidden:
        assert value not in source
