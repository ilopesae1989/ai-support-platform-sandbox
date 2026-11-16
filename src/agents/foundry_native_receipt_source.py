"""Bounded readback of stored Foundry MCP evidence under an explicit identity.

Candidate transport, not wired to a deployed attestor or the served workflow.
The governor supplies both response IDs, the native approval ID and arguments
from its durable state. Callers cannot supply URLs or provider response bodies.
Three GETs only: approval response, execution response, execution input items.

This does not sign a correlation receipt, prove backend identity, claim replay
ownership, confer approval authority or establish technical success. A provider
output still needs an exact authenticated association with a backend receipt.
Injected credentials/HTTP clients are for offline tests; deployed construction
must use build_managed_identity_native_receipt_source in an isolated host.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from decimal import Decimal
import re
from threading import Lock
from urllib.parse import urlsplit

import httpx
from azure.identity import ManagedIdentityCredential

from src.azure_key_vault_receipt_signing import ReceiptManagedIdentity
from src.workflows.incident_resolution.mcp_receipt_trust import (
    canonical_subject_v1, parse_subject_json_v1,
)

_SCOPE = "https://ai.azure.com/.default"
_LIMIT = 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z", re.ASCII)


class NativeReceiptUnavailable(RuntimeError):
    """No usable readback. No automatic retry, approval or redispatch."""


def _require(condition, code):
    if not condition:
        raise NativeReceiptUnavailable(code)


def _canonical_arguments(value):
    _require(type(value) is str, "ARGUMENTS_NOT_JSON_STRING")
    return canonical_subject_v1(parse_subject_json_v1(value.encode("utf-8")))


@dataclass(frozen=True)
class NativeReceiptReadbackPin:
    project_endpoint: str
    identity: ReceiptManagedIdentity
    approval_prompt_response_id: str
    execution_response_id: str
    approval_request_id: str
    server_label: str
    tool_name: str
    expected_arguments_json: bytes = field(repr=False)

    def __post_init__(self):
        p = urlsplit(self.project_endpoint) if type(self.project_endpoint) is str else None
        _require(p is not None and p.scheme == "https" and not p.query and not p.fragment
                 and re.fullmatch(r"[a-z0-9][a-z0-9-]*\.services\.ai\.azure\.com", p.netloc)
                 and re.fullmatch(r"/api/projects/[A-Za-z0-9][A-Za-z0-9_-]*", p.path),
                 "EXACT_PROJECT_ENDPOINT_REQUIRED")
        _require(type(self.identity) is ReceiptManagedIdentity, "EXPLICIT_IDENTITY_REQUIRED")
        for value in (self.approval_prompt_response_id, self.execution_response_id,
                      self.approval_request_id, self.server_label, self.tool_name):
            _require(type(value) is str and _ID.fullmatch(value), "INVALID_PINNED_IDENTIFIER")
        _require(len({self.approval_prompt_response_id, self.execution_response_id,
                      self.approval_request_id}) == 3, "PINNED_IDENTIFIERS_NOT_DISTINCT")
        object.__setattr__(self, "expected_arguments_json", canonical_subject_v1(
            parse_subject_json_v1(self.expected_arguments_json)))


@dataclass(frozen=True)
class NativeMcpReadback:
    """Native item consistency only, never a dispatch or acceptance authority.

    Bodies/output may contain sensitive data. They are kept in memory for the
    future authenticated attestor/custody channel, not printed or exported as
    sanitized public evidence. The object is not accepted as external input.
    """
    approval_prompt_response_id: str
    execution_response_id: str
    approval_request_id: str
    mcp_call_id: str
    server_label: str
    tool_name: str
    provider_output: str = field(repr=False)
    approval_response_bytes: bytes = field(repr=False)
    execution_response_bytes: bytes = field(repr=False)
    execution_input_bytes: bytes = field(repr=False)

    @property
    def source_sha256(self):
        return tuple(hashlib.sha256(raw).hexdigest() for raw in (
            self.approval_response_bytes, self.execution_response_bytes,
            self.execution_input_bytes))


def _parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "DUPLICATE_PROVIDER_JSON_KEY")
            result[key] = value
        return result

    def invalid(_):
        raise NativeReceiptUnavailable("NONFINITE_PROVIDER_JSON")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_float=Decimal, parse_constant=invalid)
    _require(type(value) is dict, "PROVIDER_RESPONSE_NOT_OBJECT")
    return value


def _items(value, field_name):
    items = value.get(field_name)
    _require(type(items) is list and len(items) <= 100
             and all(type(x) is dict for x in items), "PROVIDER_ITEMS_INVALID")
    ids = [item.get("id") for item in items if item.get("id") is not None]
    _require(all(type(x) is str for x in ids) and len(ids) == len(set(ids)),
             "DUPLICATE_PROVIDER_ITEM_ID")
    return items


def _single(items, kind):
    selected = [x for x in items if x.get("type") == kind]
    _require(len(selected) == 1, "EXPECTED_ONE_" + kind.upper())
    return selected[0]


class FoundryNativeReceiptSource:
    def __init__(self, *, pin, credential, client):
        _require(type(pin) is NativeReceiptReadbackPin, "READBACK_PIN_REQUIRED")
        self._pin, self._credential, self._client = pin, credential, client
        self._lock, self._consumed = Lock(), False

    @property
    def pin(self):
        return self._pin

    def _get(self, path, token):
        url = self._pin.project_endpoint + "/openai/v1/responses/" + path
        with self._client.stream("GET", url, headers={
                "Authorization": "Bearer " + token, "Accept": "application/json"},
                follow_redirects=False) as response:
            _require(response.status_code == 200, "PROVIDER_GET_HTTP_STATUS")
            parts, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                _require(size <= _LIMIT, "PROVIDER_REPLY_TOO_LARGE")
                parts.append(chunk)
            raw = b"".join(parts)
        return _parse(raw), raw

    def read_once(self):
        with self._lock:
            _require(not self._consumed, "READBACK_ATTEMPT_ALREADY_CONSUMED")
            self._consumed = True
        try:
            p = self._pin
            token = self._credential.get_token(_SCOPE).token
            _require(type(token) is str and 0 < len(token) <= 65536
                     and all(32 < ord(c) < 127 for c in token), "INVALID_ACCESS_TOKEN")
            approval, approval_raw = self._get(p.approval_prompt_response_id, token)
            _require(approval.get("id") == p.approval_prompt_response_id
                     and approval.get("object") == "response"
                     and approval.get("status") == "completed"
                     and approval.get("error") is None, "APPROVAL_RESPONSE_MISMATCH")
            approval_items = _items(approval, "output")
            _require(not any(x.get("type") == "mcp_call" for x in approval_items),
                     "CALL_PRESENT_AT_APPROVAL_PAUSE")
            request = _single(approval_items, "mcp_approval_request")
            _require(request.get("id") == p.approval_request_id
                     and request.get("server_label") == p.server_label
                     and request.get("name") == p.tool_name
                     and _canonical_arguments(request.get("arguments")) == p.expected_arguments_json,
                     "NATIVE_APPROVAL_REQUEST_MISMATCH")

            execution, execution_raw = self._get(p.execution_response_id, token)
            _require(execution.get("id") == p.execution_response_id
                     and execution.get("object") == "response"
                     and execution.get("status") == "completed"
                     and execution.get("error") is None, "EXECUTION_RESPONSE_MISMATCH")
            previous = execution.get("previous_response_id")
            # Conversation-based SDK continuations need not set previous_response_id.
            # If supplied, it must agree; native input approval below is required.
            _require(previous is None or previous == p.approval_prompt_response_id,
                     "PREVIOUS_RESPONSE_MISMATCH")
            output_items = _items(execution, "output")
            _require(not any(x.get("type") == "mcp_approval_request" for x in output_items),
                     "EXECUTION_STILL_REQUIRES_APPROVAL")
            call = _single(output_items, "mcp_call")
            _require(type(call.get("id")) is str and _ID.fullmatch(call["id"])
                     and call["id"] not in (p.approval_request_id, p.approval_prompt_response_id,
                                            p.execution_response_id)
                     and call.get("approval_request_id") == p.approval_request_id
                     and call.get("server_label") == p.server_label
                     and call.get("name") == p.tool_name
                     and _canonical_arguments(call.get("arguments")) == p.expected_arguments_json,
                     "NATIVE_MCP_CALL_MISMATCH")
            _require(call.get("status") in (None, "completed") and call.get("error") is None
                     and type(call.get("output")) is str, "MCP_CALL_NOT_COMPLETED_OUTPUT")

            inputs, inputs_raw = self._get(p.execution_response_id + "/input_items?limit=100&order=asc", token)
            _require(inputs.get("object") == "list" and inputs.get("has_more") is False,
                     "INPUT_ITEMS_INCOMPLETE")
            input_items = _items(inputs, "data")
            decision = _single([x for x in input_items if
                x.get("approval_request_id") == p.approval_request_id], "mcp_approval_response")
            _require(decision.get("approve") is True, "NATIVE_APPROVAL_NOT_TRUE")
            # Never treat caller-supplied historical input mcp_call as this output.
            return NativeMcpReadback(p.approval_prompt_response_id, p.execution_response_id,
                p.approval_request_id, call["id"], p.server_label, p.tool_name, call["output"],
                approval_raw, execution_raw, inputs_raw)
        except NativeReceiptUnavailable:
            raise
        except Exception:
            raise NativeReceiptUnavailable("PROVIDER_READBACK_UNAVAILABLE_NO_RETRY") from None

    def close(self):
        try:
            self._client.close()
        finally:
            self._credential.close()


def build_managed_identity_native_receipt_source(pin):
    """Construct with no I/O; explicit MI, HTTPS verification, no proxy/retry."""
    _require(type(pin) is NativeReceiptReadbackPin, "READBACK_PIN_REQUIRED")
    identity_options = {} if pin.identity.kind == "system_assigned" else {
        "client_id": pin.identity.client_id}
    credential = ManagedIdentityCredential(retry_total=0, **identity_options)
    try:
        client = httpx.Client(transport=httpx.HTTPTransport(retries=0),
                              timeout=20.0, trust_env=False, follow_redirects=False)
    except Exception:
        credential.close()
        raise
    return FoundryNativeReceiptSource(pin=pin, credential=credential, client=client)
