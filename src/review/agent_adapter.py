"""Bounded, one-call Reviewer response adapter; no quality verdict or runtime wiring."""
from __future__ import annotations

import asyncio
import json
import math

from pydantic import ValidationError

from .contracts import ReviewRequest, ReviewResult
from .policy import review_request_sha256


class ReviewAgentAdapterError(RuntimeError):
    """Stable error code only; never include a provider message or response body."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        # json has already decoded escapes in names before calling this hook.
        if key in result:
            raise ValueError("Duplicate JSON member.")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError("Nonfinite JSON constant.")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite JSON number.")
    return number


class ReviewAgentAdapter:
    """Send one copied request to an injected runner and validate its text output.

    The caller owns the runner, its configuration and lifecycle. This adapter
    creates no sessions, stores no request history and adds no invocation options.
    It does not verify the runner's cloud-side tools or provider retry policy.

    The timeout is cooperative: Python cancellation does not prove that an
    already received remote request has stopped. No retry occurs in this adapter.
    Correlation, coverage and evidence acceptance remain in assess_review().
    """

    def __init__(
        self,
        *,
        runner: object,
        timeout_seconds: float = 30.0,
        max_request_bytes: int = 65_536,
        max_response_bytes: int = 65_536,
    ) -> None:
        run = getattr(runner, "run", None)
        if not callable(run):
            raise TypeError("runner must expose callable run().")
        if type(timeout_seconds) not in (int, float):
            raise TypeError("timeout_seconds must be numeric, not boolean.")
        try:
            timeout = float(timeout_seconds)
        except (OverflowError, ValueError):
            raise ValueError("timeout_seconds must be positive and finite.") from None
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be positive and finite.")
        for limit in (max_request_bytes, max_response_bytes):
            if type(limit) is not int:
                raise TypeError("Byte limits must be integers, not booleans.")
            if limit <= 0:
                raise ValueError("Byte limits must be positive.")
        self._run = run
        self._timeout_seconds = timeout
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes

    async def run(self, request: ReviewRequest) -> ReviewResult:
        if type(request) is not ReviewRequest:
            raise TypeError("request must be exactly ReviewRequest.")
        # Revalidate forged/model_copy instances and isolate mutable nested lists.
        snapshot = ReviewRequest.model_validate(request).model_copy(deep=True)
        try:
            text_request = json.dumps(
                {
                    "request": snapshot.model_dump(mode="json"),
                    "request_sha256": review_request_sha256(snapshot),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            request_size = len(text_request.encode("utf-8"))
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ReviewAgentAdapterError("invalid_request_text") from None
        if request_size > self._max_request_bytes:
            raise ReviewAgentAdapterError("request_too_large")

        timeout_scope = asyncio.timeout(self._timeout_seconds)
        try:
            async with timeout_scope:
                response = await self._run(text_request)
        except asyncio.CancelledError:
            # Preserve external cancellation; never translate it into a verdict.
            raise
        except TimeoutError:
            code = "timeout" if timeout_scope.expired() else "runner_failed"
            raise ReviewAgentAdapterError(code) from None
        except Exception:
            raise ReviewAgentAdapterError("runner_failed") from None
        if timeout_scope.expired():
            # A runner that swallows cancellation must not create a late success.
            raise ReviewAgentAdapterError("timeout")

        try:
            text = getattr(response, "text", None)
        except Exception:
            raise ReviewAgentAdapterError("invalid_response_text") from None
        if type(text) is not str or not text.strip():
            raise ReviewAgentAdapterError("invalid_response_text")
        try:
            response_size = len(text.encode("utf-8"))
        except UnicodeError:
            raise ReviewAgentAdapterError("invalid_response_text") from None
        if response_size > self._max_response_bytes:
            raise ReviewAgentAdapterError("response_too_large")

        try:
            payload = json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
                parse_float=_finite_float,
            )
            # Reject escaped lone surrogates as well as invalid UTF-8 above.
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ReviewAgentAdapterError("invalid_json") from None
        if type(payload) is not dict:
            raise ReviewAgentAdapterError("invalid_response_contract")
        try:
            return ReviewResult.model_validate(payload)
        except (ValidationError, ValueError, TypeError, RecursionError):
            raise ReviewAgentAdapterError("invalid_response_contract") from None
