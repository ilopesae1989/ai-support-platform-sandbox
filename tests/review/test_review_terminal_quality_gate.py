from __future__ import annotations

import asyncio
import importlib
import inspect
from types import SimpleNamespace

import pytest


MISSING = "F24_REVIEW_QUALITY_GATE_NOT_IMPLEMENTED"


def _api():
    module = importlib.import_module(
        "src.channels.teams.incident_terminal_presenter"
    )

    notify = getattr(
        module,
        "notify_teams_incident_terminal_result",
        None,
    )

    if not callable(notify):
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    signature = inspect.signature(
        notify
    )

    if "review_runner" not in signature.parameters:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return module, notify


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


def _runtime_bundle():
    from tests.channels.teams.test_incident_terminal_communication import (
        _communication_result,
        _processed,
        _safe_context,
    )
    from tests.channels.teams.test_incident_terminal_presenter import (
        _invocation,
        _state,
    )

    return {
        "invocation": _invocation(),
        "state": _state(),
        "processed": _processed(),
        "candidate": _communication_result(),
        "safe_context": _safe_context(),
    }


def _rejected_bundle():
    from src.channels.teams.approval_authorization import (
        AuthorizedTeamsApprovalInvocation,
    )
    from src.channels.teams.operator_identity import (
        TeamsOperatorIdentity,
    )
    from src.runtime.procedure.approval_channel import (
        ApprovalChannelAction,
        ApprovalDecision,
    )
    from src.runtime.procedure.workflow import (
        ApprovalOutcome,
    )
    from tests.channels.teams.test_incident_terminal_communication import (
        _communication_result,
        _safe_context,
    )
    from tests.channels.teams.test_incident_terminal_presenter import (
        _invocation,
    )

    base = _invocation()

    invocation = AuthorizedTeamsApprovalInvocation(
        policy_id=base.policy_id,
        operator=TeamsOperatorIdentity(
            **base.operator.model_dump()
        ),
        action=ApprovalChannelAction(
            approval_id=(
                base.action.approval_id
            ),
            decision=ApprovalDecision.REJECT,
        ),
    )

    processed = SimpleNamespace(
        workflow_result=ApprovalOutcome(
            workflow_id="wf-quality-gate-reject",
            approved=False,
            status="blocked",
        ),
        safe_communication_context=_safe_context(),
    )

    return {
        "invocation": invocation,
        "processed": processed,
        "candidate": _communication_result(),
    }


def _review_result(
    review_request,
    *,
    outcome="pass",
    mismatch=False,
):
    from src.review.contracts import (
        REQUIRED_REVIEW_CRITERIA,
        ReviewResult,
    )
    from src.review.policy import (
        review_request_sha256,
    )

    findings = []

    for index, criterion in enumerate(
        REQUIRED_REVIEW_CRITERIA
    ):
        criterion_outcome = (
            outcome
            if index == 0
            else "pass"
        )

        findings.append(
            {
                "criterion": criterion,
                "outcome": criterion_outcome,
                "reason": (
                    "Synthetic quality-gate finding "
                    "for deterministic integration testing."
                ),
                "evidence_refs": [
                    "/candidate/summary",
                ],
            }
        )

    payload = {
        "review_id": (
            "review-quality-gate-mismatch"
            if mismatch
            else review_request.review_id
        ),
        "request_sha256": (
            review_request_sha256(
                review_request
            )
        ),
        "criteria_version": (
            review_request.criteria_version
        ),
        "findings": findings,
    }

    return ReviewResult.model_validate(
        payload
    )


def _expected_candidate_text(candidate):
    return "\n".join(
        [
            candidate.headline,
            candidate.summary,
            *[
                f"- {detail}"
                for detail in candidate.details
            ],
        ]
    )


def test_presenter_exposes_optional_keyword_only_review_runner():
    _, notify = _api()

    parameter = inspect.signature(
        notify
    ).parameters["review_runner"]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert parameter.default is None


def test_missing_reviewer_skips_communication_and_uses_runtime_fallback(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()

    communication_calls = []
    sent = {}

    async def communication_runner(request):
        communication_calls.append(
            request
        )
        return bundle["candidate"]

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    result = run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=None,
        )
    )

    assert result == "sent"
    assert communication_calls == []
    assert sent["text"] == (
        module.render_incident_terminal_result(
            bundle["state"]
        )
    )


def test_pass_review_publishes_runtime_candidate(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    review_calls = []
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        review_calls.append(
            request
        )
        return _review_result(
            request,
            outcome="pass",
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert len(review_calls) == 1
    assert sent["text"] == (
        _expected_candidate_text(
            bundle["candidate"]
        )
    )


@pytest.mark.parametrize(
    "outcome",
    [
        "fail",
        "inconclusive",
    ],
)
def test_nonpass_review_uses_runtime_deterministic_fallback(
    monkeypatch,
    run_async,
    outcome,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome=outcome,
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert sent["text"] == (
        module.render_incident_terminal_result(
            bundle["state"]
        )
    )


def test_review_exception_uses_runtime_fallback_and_is_not_retried(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    review_calls = []
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        review_calls.append(
            request
        )
        raise RuntimeError(
            "synthetic reviewer unavailable"
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert len(review_calls) == 1
    assert sent["text"] == (
        module.render_incident_terminal_result(
            bundle["state"]
        )
    )


def test_communication_exception_skips_review_and_uses_runtime_fallback(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    review_calls = []
    sent = {}

    async def communication_runner(request):
        raise RuntimeError(
            "synthetic communication unavailable"
        )

    async def review_runner(request):
        review_calls.append(
            request
        )
        raise AssertionError(
            "review must not run without candidate"
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert review_calls == []
    assert sent["text"] == (
        module.render_incident_terminal_result(
            bundle["state"]
        )
    )


def test_review_request_contains_only_governed_context_and_candidate(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    captured = {}

    async def communication_runner(request):
        captured["communication_request"] = (
            request
        )
        return bundle["candidate"]

    async def review_runner(request):
        captured["review_request"] = request
        return _review_result(
            request,
            outcome="pass",
        )

    async def fake_send(**kwargs):
        captured["send"] = kwargs
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    from src.review.contracts import (
        ReviewRequest,
    )

    request = captured[
        "review_request"
    ]

    assert type(request) is ReviewRequest

    assert (
        request.context.model_dump(
            mode="json"
        )
        == captured[
            "communication_request"
        ].model_dump(
            mode="json"
        )
    )

    assert (
        request.candidate.model_dump(
            mode="json"
        )
        == bundle[
            "candidate"
        ].model_dump(
            mode="json"
        )
    )

    serialized = repr(
        request.model_dump(
            mode="json"
        )
    )

    for forbidden in (
        "conversation-terminal-test",
        "apr-terminal-test",
        "resolved_parameters",
        "operation_action",
        "capability_id",
        "target_resource",
    ):
        assert forbidden not in serialized


def test_review_correlation_mismatch_falls_back_via_python_policy(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome="pass",
            mismatch=True,
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert sent["text"] == (
        module.render_incident_terminal_result(
            bundle["state"]
        )
    )


def test_rejected_approval_pass_review_publishes_candidate(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _rejected_bundle()
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome="pass",
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert sent["text"] == (
        _expected_candidate_text(
            bundle["candidate"]
        )
    )


def test_rejected_approval_failed_review_uses_deterministic_reject_fallback(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _rejected_bundle()
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome="fail",
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert sent["text"] == (
        "⛔ Operación rechazada.\n"
        "No se ha ejecutado la acción solicitada.\n"
        "Procedimiento: PROC-TERMINAL-001 - "
        "Procedimiento terminal test"
    )


def test_review_gate_preserves_authorized_teams_destination(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()
    sent = {}

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome="pass",
        )

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert sent["tenant_id"] == (
        bundle[
            "invocation"
        ].operator.tenant_id
    )
    assert sent["conversation_id"] == (
        bundle[
            "invocation"
        ].operator.conversation_id
    )


def test_review_gate_does_not_mutate_context_or_candidate(
    monkeypatch,
    run_async,
):
    module, notify = _api()
    bundle = _runtime_bundle()

    before_context = (
        bundle[
            "processed"
        ].safe_communication_context.model_dump(
            mode="json"
        )
    )
    before_candidate = (
        bundle["candidate"].model_dump(
            mode="json"
        )
    )

    async def communication_runner(request):
        return bundle["candidate"]

    async def review_runner(request):
        return _review_result(
            request,
            outcome="pass",
        )

    async def fake_send(**kwargs):
        return "sent"

    monkeypatch.setattr(
        module,
        "send_teams_message",
        fake_send,
    )

    run_async(
        notify(
            invocation=bundle["invocation"],
            processed=bundle["processed"],
            outbound=object(),
            communication_runner=communication_runner,
            review_runner=review_runner,
        )
    )

    assert (
        bundle[
            "processed"
        ].safe_communication_context.model_dump(
            mode="json"
        )
        == before_context
    )
    assert (
        bundle["candidate"].model_dump(
            mode="json"
        )
        == before_candidate
    )


def test_presenter_review_boundary_is_injected_and_non_authoritative():
    module, notify = _api()

    source = inspect.getsource(
        notify
    ).casefold()

    required = {
        "review_runner",
        "build_review_request",
        "assess_review",
        "communication_runner",
        "send_teams_message",
        "render_incident_terminal_result",
        "_render_rejected_communication_request",
    }

    for value in required:
        assert value in source

    forbidden = {
        "foundryagents",
        "reviewagentadapter",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "run_review",
    }

    for value in forbidden:
        assert value not in source
