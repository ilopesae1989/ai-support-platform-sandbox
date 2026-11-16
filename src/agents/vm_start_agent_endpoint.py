"""Dedicated WRITE agent endpoint adapter; no request is sent by this factory.

Pinned to agent-framework-foundry 1.10.4. ``client_type``/``project_client``
are supported constructor seams; overriding ``_prepare_options`` is a protected,
version-specific extension, not a promise of compatibility with future SDKs.
This selects the documented v1 endpoint. It does not prove Azure RBAC coverage,
GET provenance, caller exclusivity, tool authority, or successful VM execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import version
import re
from types import SimpleNamespace


SDK_PIN = "1.10.4"
VERSION_HEADER = "x-agent-version-override"
_RESERVED_HEADERS = frozenset({VERSION_HEADER, "authorization", "api-key", "host",
                               "foundry-features", "x-ms-authorization-auxiliary"})
_TRANSPORT_KEYS = frozenset({"base_url", "api_key", "api_version", "project_endpoint",
                            "agent_name", "agent_version", "client", "async_client"})


def _load_sdk_types():
    if version("agent-framework-foundry") != SDK_PIN:
        raise RuntimeError("STOP_WRITE_ENDPOINT_SDK_PIN")
    from agent_framework import FunctionInvocationLayer, ChatMiddlewareLayer
    from agent_framework.observability import ChatTelemetryLayer
    from agent_framework.foundry import FoundryAgent, RawFoundryAgentChatClient
    from azure.ai.projects.aio import AIProjectClient
    return SimpleNamespace(Agent=FoundryAgent, Raw=RawFoundryAgentChatClient,
                           Functions=FunctionInvocationLayer, Middleware=ChatMiddlewareLayer,
                           Telemetry=ChatTelemetryLayer, Project=AIProjectClient)


def _reject_transport_overrides(options, kwargs):
    for source in (options, kwargs):
        if not isinstance(source, Mapping):
            raise ValueError("STOP_WRITE_ENDPOINT_OPTIONS_SHAPE")
        if _TRANSPORT_KEYS.intersection(source):
            raise ValueError("STOP_WRITE_ENDPOINT_TRANSPORT_OVERRIDE")
        headers = source.get("extra_headers")
        if headers is not None:
            if not isinstance(headers, Mapping) or any(not isinstance(k, str) for k in headers):
                raise ValueError("STOP_WRITE_ENDPOINT_HEADERS_SHAPE")
            if any(k.lower() in _RESERVED_HEADERS for k in headers):
                raise ValueError("STOP_WRITE_ENDPOINT_ROUTING_HEADER_OVERRIDE")
        if source.get("extra_query"):
            raise ValueError("STOP_WRITE_ENDPOINT_QUERY_OVERRIDE")
        extra_body = source.get("extra_body")
        if extra_body is not None:
            if not isinstance(extra_body, Mapping):
                raise ValueError("STOP_WRITE_ENDPOINT_EXTRA_BODY_SHAPE")
            if "agent_session_id" in extra_body:
                raise ValueError("STOP_WRITE_ENDPOINT_HOSTED_SESSION_OVERRIDE")


def build_vm_start_agent_endpoint(*, definition, project_endpoint: str, credential,
                                  agent_openai_endpoint: str | None = None):
    """Build the opt-in WRITE FoundryAgent while retaining its session machinery.

    The optional URL must equal the documented project/name endpoint exactly.
    Without it the same documented SDK rule is used; that is an expected URL,
    never a claim that a GET observed or authorized it. Credentials are supplied
    by the composition root; this module never chooses an operator credential.
    """
    name, pin = getattr(definition, "name", None), getattr(definition, "version", None)
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", name):
        raise ValueError("STOP_WRITE_ENDPOINT_AGENT_NAME")
    if not isinstance(pin, str) or not re.fullmatch(r"[1-9][0-9]*", pin):
        raise ValueError("STOP_WRITE_ENDPOINT_VERSION_PIN")
    if not isinstance(project_endpoint, str) or not re.fullmatch(
        r"https://[A-Za-z0-9-]+\.services\.ai\.azure\.com/api/projects/[A-Za-z0-9_-]+/?", project_endpoint
    ):
        raise ValueError("STOP_WRITE_ENDPOINT_PROJECT_URL")
    if credential is None:
        raise ValueError("STOP_WRITE_ENDPOINT_CREDENTIAL_REQUIRED")
    project = project_endpoint.removesuffix("/")
    endpoint = f"{project}/agents/{name}/endpoint/protocols/openai"
    if agent_openai_endpoint is not None and agent_openai_endpoint != endpoint:
        raise ValueError("STOP_WRITE_ENDPOINT_URL_MISMATCH")
    sdk = _load_sdk_types()

    class BoundProject(sdk.Project):
        def get_openai_client(self, *, agent_name=None, **kwargs):
            if agent_name is not None or any(k in kwargs for k in ("base_url", "api_key", "default_query")):
                raise ValueError("STOP_WRITE_ENDPOINT_CLIENT_ROUTING_OVERRIDE")
            headers = dict(kwargs.pop("default_headers", None) or {})
            if any(not isinstance(k, str) or k.lower() in _RESERVED_HEADERS for k in headers):
                raise ValueError("STOP_WRITE_ENDPOINT_CLIENT_HEADER_OVERRIDE")
            headers[VERSION_HEADER] = pin
            return super().get_openai_client(
                base_url=endpoint, default_query={"api-version": "v1"},
                default_headers=headers, **kwargs,
            )

    class BoundChatClient(sdk.Functions, sdk.Middleware, sdk.Telemetry, sdk.Raw):
        def __init__(self, **kwargs):
            if (kwargs.get("allow_preview") is not False
                    or kwargs.get("project_client") is not None
                    or kwargs.get("agent_name") != name
                    or kwargs.get("agent_version") != pin
                    or kwargs.get("project_endpoint") != project):
                raise ValueError("STOP_WRITE_ENDPOINT_CLIENT_BINDING")
            self.write_endpoint_project = BoundProject(endpoint=project, credential=credential,
                                                       allow_preview=False, api_version="v1")
            kwargs["project_client"] = self.write_endpoint_project
            super().__init__(**kwargs)

        async def _prepare_options(self, messages, options, **kwargs):
            _reject_transport_overrides(options, kwargs)
            prepared = await super()._prepare_options(messages, options, **kwargs)
            if not isinstance(prepared, Mapping):
                raise ValueError("STOP_WRITE_ENDPOINT_PREPARED_SHAPE")
            result = dict(prepared)
            _reject_transport_overrides(result, {})
            body = result.get("extra_body")
            if not isinstance(body, Mapping):
                raise ValueError("STOP_WRITE_ENDPOINT_AGENT_REFERENCE_MISSING")
            expected = {"type": "agent_reference", "name": name, "version": pin}
            if body.get("agent_reference") != expected:
                raise ValueError("STOP_WRITE_ENDPOINT_AGENT_REFERENCE_MISMATCH")
            body = dict(body)
            del body["agent_reference"]
            if body:
                result["extra_body"] = body
            else:
                result.pop("extra_body", None)
            headers = dict(result.get("extra_headers") or {})
            headers[VERSION_HEADER] = pin
            result["extra_headers"] = headers
            return result

        async def close(self):
            try:
                await super().close()
            finally:
                await self.write_endpoint_project.close()

    return sdk.Agent(
        project_endpoint=project, agent_name=name, agent_version=pin,
        credential=credential, allow_preview=False, client_type=BoundChatClient,
        default_options={"extra_body": {"max_tool_calls": 1, "parallel_tool_calls": False}},
        timeout=120.0,
    )
