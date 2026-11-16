"""Deterministic content acceptance for the governed RG List procedure.

This validates the registered operation's content. It does not authenticate a
backend, attest inventory completeness, or replace the independent H11 receipts.
The READ authority registry supplies the selected server and argument contract.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import re

from .azure_read_tool_authority import (
    AzureReadToolAuthority, build_default_azure_read_tool_authority_registry,
)
from .operation_models import OperationResult


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate result key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("Non-finite result constant")


def _payload(value, depth=0):
    if depth > 4:
        raise ValueError("Result envelope too deep")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > 1_000_000:
            raise ValueError("Result envelope too large")
        return _payload(json.loads(value, object_pairs_hook=_unique_pairs,
                                   parse_constant=_invalid_constant), depth + 1)
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError("Exactly one result envelope required")
        return _payload(value[0], depth + 1)
    if not isinstance(value, Mapping):
        raise ValueError("Result is not an object")
    if value.get("type") == "text":
        if not isinstance(value.get("text"), str) or "status" in value or "results" in value:
            raise ValueError("Ambiguous text envelope")
        return _payload(value["text"], depth + 1)
    return value


def _text(value):
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def rg_list_content_accepted(
    result: OperationResult, *, authority: AzureReadToolAuthority | None = None,
) -> bool:
    """True only for one exact group_list call with a complete supported body.

    An empty groups array is a valid empty inventory. A missing array, partial
    page, bare success status, unsupported encoding or cross-subscription item
    cannot satisfy the procedure. No result creates operational authority.
    """
    # Direct historical callers retain their explicit legacy contract. Product
    # composition injects the selected authority; never derive it from output.
    if authority is None:
        authority = build_default_azure_read_tool_authority_registry().get("azure.resource_group.list")
    if not isinstance(authority, AzureReadToolAuthority):
        raise TypeError("authority must be AzureReadToolAuthority.")
    if (result.capability_id != authority.capability_id
            or result.operation_domain != authority.operation_domain
            or result.operation_kind != "read"
            or result.operation_action != authority.operation_action
            or result.target_resource != authority.target_resource
            or tuple(result.required_parameters) != authority.required_parameters
            or tuple(p.name for p in result.resolved_parameters) != authority.required_parameters):
        return False
    resolved = {p.name: p.value for p in result.resolved_parameters}
    subscription = resolved["subscription_id"]
    if not isinstance(subscription, str) or not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", subscription):
        return False
    proof = result.evidence
    if (proof is None or len(proof.mcp_calls) != 1 or len(proof.mcp_results) != 1
            or proof.tool_calls or proof.tool_results or proof.response_errors):
        return False
    call, response = proof.mcp_calls[0], proof.mcp_results[0]
    expected_arguments = {argument: resolved[parameter] for argument, parameter in authority.argument_bindings}
    if (call.mcp_call_id != response.mcp_call_id or call.tool_name != authority.tool_name
            or call.server_name != authority.server_label or dict(call.arguments) != expected_arguments):
        return False
    try:
        body = _payload(response.output)
        if (type(body.get("status")) is not int or body["status"] != 200
                or body.get("isError", False) is not False or body.get("error") is not None
                or body.get("nextLink") not in (None, "")):
            return False
        content = body.get("results")
        if not isinstance(content, Mapping) or content.get("nextLink") not in (None, ""):
            return False
        groups = content.get("groups")
        if not isinstance(groups, (list, tuple)) or len(groups) > 10_000:
            return False
        seen = set()
        for group in groups:
            if not isinstance(group, Mapping) or not all(_text(group.get(k)) for k in ("name", "id", "location")):
                return False
            name, resource_id = group["name"], group["id"]
            if any(c in name for c in "/\\%?#"):
                return False
            expected = "/subscriptions/" + subscription + "/resourceGroups/" + name
            if resource_id != expected or resource_id.casefold() in seen:
                return False
            seen.add(resource_id.casefold())
        return True
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return False
