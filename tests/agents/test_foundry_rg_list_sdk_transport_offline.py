"""F27-B02-2.6-T05: SDK real con transporte HTTP exclusivamente sintético.

Se usa la binding configurada y el helper de producto con T07 aplicado. No se
sustituyen FoundryAgent, run, el parser MCP ni el serializador del SDK. Solo se
sustituyen las fronteras de credencial y transporte y se bloquean efectos.

La prueba acredita referencia solicitada, opciones por solicitud y continuidad
nativa. No acredita selección del servicio, definición remota, dispatch, un
presupuesto global del workflow ni el runner PENDING reservado para 2.7.
"""

from __future__ import annotations

import asyncio
import hashlib
from importlib import metadata
import json
import os
import socket
import subprocess
import sys


_SDK_VERSIONS = {
    "agent-framework-core": "1.13.0",
    "agent-framework-foundry": "1.10.4",
    "agent-framework-openai": "1.12.0",
    "azure-ai-projects": "2.3.0",
    "azure-identity": "1.25.3",
    "openai": "2.53.0",
    "httpx": "0.28.1",
}
_SANDBOX_ENDPOINT = (
    "https://aif-icenter-sbx-eus2.services.ai.azure.com"
    "/api/projects/aifproj-icenter-sbx"
)
_OFFLINE_ENDPOINT = (
    "https://f27-b02-2-6-offline.invalid/api/projects/synthetic-project"
)
_DUMMY_AUTH = "F27_2_6_OFFLINE_LITERAL_NOT_A_CREDENTIAL"
_APPROVAL_ID = "mcpr_f27_2_6_offline_01"
_FIRST_RESPONSE_ID = "resp_f27_2_6_offline_01"
_SECOND_RESPONSE_ID = "resp_f27_2_6_offline_02"
_SYNTHETIC_SUBSCRIPTION = "11111111-2222-4333-8444-555555555555"
_PROMPT = "F27 2.6 OFFLINE transport fixture. No service or operational request."


class _OfflineBoundaryViolation(BaseException):
    """No permite que un catch/retry del SDK absorba una frontera prohibida."""


def test_configured_read_binding_serializes_version_limits_and_native_continuation(
    monkeypatch,
    request,
):
    # Son las versiones de transporte observadas en Windows R4. No se instalan
    # dependencias ni se permite un fallback a un SDK falso o a otra versión.
    assert {
        package: metadata.version(package)
        for package in _SDK_VERSIONS
    } == _SDK_VERSIONS

    for name, value in {
        "OTEL_SDK_DISABLED": "true",
        "AGENT_FRAMEWORK_USER_AGENT_DISABLED": "true",
        "AGENT_FRAMEWORK_FEATURE_MASK_DISABLED": "true",
        "AZURE_TRACING_ENABLED": "false",
        "AZURE_AI_PROJECTS_CONSOLE_LOGGING": "false",
    }.items():
        monkeypatch.setenv(name, value)

    denied_attempts = []

    def denied(boundary):
        def fail(*args, **kwargs):
            denied_attempts.append(boundary)
            raise _OfflineBoundaryViolation(boundary)

        return fail

    # El runner focal aporta su política asyncio sin sockets. Este test la
    # conserva y deniega conexiones, resolución, procesos y HTTP reales.
    monkeypatch.setattr(socket.socket, "connect", denied("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", denied("socket.connect_ex"))
    monkeypatch.setattr(socket.socket, "sendto", denied("socket.sendto"))
    monkeypatch.setattr(socket, "create_connection", denied("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", denied("getaddrinfo"))
    monkeypatch.setattr(subprocess, "Popen", denied("subprocess.Popen"))
    monkeypatch.setattr(os, "system", denied("os.system"))

    import httpx
    from agent_framework import Content, FunctionTool
    from agent_framework_foundry import _agent as foundry_sdk
    from agent_framework_openai import _feature_usage as feature_usage
    from azure.ai.projects.aio import _patch as project_sdk
    from openai import _base_client as openai_base

    from src.agents import production_communication_runner as production_factory
    from src.agents.catalog import AgentKey
    from src.agents.production_settings import FoundryProductionSettings
    from src.config.foundry_capability_bindings import (
        build_capability_foundry_agent_binding_registry,
    )

    monkeypatch.setattr(
        httpx.HTTPTransport, "handle_request", denied("HTTPTransport")
    )
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport,
        "handle_async_request",
        denied("AsyncHTTPTransport"),
    )
    monkeypatch.setattr(FunctionTool, "invoke", denied("FunctionTool.invoke"))

    registry = build_capability_foundry_agent_binding_registry(
        {
            "FOUNDRY_CAPABILITY_BINDING_PROFILE": "azure-resource-group-list-sbx-v1",
            "FOUNDRY_PROJECT_ENDPOINT": _SANDBOX_ENDPOINT,
        }
    )
    binding = registry.get("azure.resource_group.list")
    definition = registry.resolve(
        capability=binding.capability,
        read_tool_authority=binding.read_tool_authority,
    )
    assert definition is binding.agent_definition
    assert definition.key is AgentKey.AZURE_OPERATIONS
    assert definition.name == "agent-azure-operations-rg-list-sbx"
    assert definition.version == "1"
    assert binding.require_approval == "always"
    authority = binding.read_tool_authority
    assert authority.server_label == "azure-mcp-operations-sbx"
    assert authority.tool_name == "group_list"
    assert authority.argument_bindings == (("subscription", "subscription_id"),)
    # Datos de prueba explícitos, no parámetros deducidos de un recurso real.
    governed_fixture_parameters = {"subscription_id": _SYNTHETIC_SUBSCRIPTION}
    tool_arguments = {
        argument: governed_fixture_parameters[parameter]
        for argument, parameter in authority.argument_bindings
    }

    class NoCredential:
        get_token = denied("credential.get_token")
        get_token_info = denied("credential.get_token_info")

    credential = NoCredential()
    monkeypatch.setattr(
        production_factory,
        "build_foundry_production_credential",
        lambda settings: credential,
    )

    def dummy_api_key(self, kwargs):
        assert "api_key" not in kwargs
        return _DUMMY_AUTH

    monkeypatch.setattr(project_sdk.AIProjectClient, "_get_openai_api_key", dummy_api_key)

    # La detección de plataforma puede ejecutar uname -p en Linux. Solo esa
    # metadata de cabecera es sintética; no cambia cuerpos ni serializadores.
    # El wrapper evita además el executor usado para obtener esa metadata.
    original_asyncify = openai_base.asyncify

    def synthetic_platform():
        return "Unknown"

    def local_platform_asyncify(function):
        if function is synthetic_platform:
            async def local_platform():
                return synthetic_platform()

            return local_platform
        return original_asyncify(function)

    monkeypatch.setattr(openai_base, "get_platform", synthetic_platform)
    monkeypatch.setattr(openai_base, "asyncify", local_platform_asyncify)

    captures = []
    capture_evidence = []
    synthetic_attempts = []
    native_evidence = {}

    def response_fixture(index):
        if index == 1:
            output = [
                {
                    "type": "mcp_approval_request",
                    "id": _APPROVAL_ID,
                    "name": authority.tool_name,
                    "arguments": json.dumps(tool_arguments, separators=(",", ":")),
                    "server_label": authority.server_label,
                }
            ]
        else:
            output = [
                {
                    "type": "message",
                    "id": "msg_f27_2_6_offline_02",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "OFFLINE_SYNTHETIC_REJECTION_COMPLETE",
                            "annotations": [],
                        }
                    ],
                }
            ]
        return {
            "id": _FIRST_RESPONSE_ID if index == 1 else _SECOND_RESPONSE_ID,
            "object": "response",
            "created_at": 1792540800.0,
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "instructions": None,
            "model": "f27-offline-model",
            "output": output,
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "store": True,
            "temperature": 1.0,
            "top_p": 1.0,
            "truncation": "disabled",
            "usage": None,
            "metadata": {},
            "conversation": None,
            "previous_response_id": None,
        }

    def capture_handler(request):
        # Límite del fixture, no garantía de presupuesto global del producto.
        synthetic_attempts.append((request.method, str(request.url)))
        if len(synthetic_attempts) > 2:
            denied("third_synthetic_request")()
        if (
            request.method != "POST"
            or str(request.url) != _OFFLINE_ENDPOINT + "/openai/v1/responses"
            or request.headers.get("authorization") != "Bearer " + _DUMMY_AUTH
            or request.headers.get("x-stainless-retry-count") not in (None, "0")
        ):
            denied("unexpected_synthetic_request")()
        raw_body = request.content
        assert _DUMMY_AUTH.encode("ascii") not in raw_body
        # Captura posterior a la serialización real HTTPX/OpenAI; no kwargs de
        # constructor ni un cuerpo elaborado por el propio test.
        captures.append(json.loads(raw_body.decode("utf-8")))
        capture_evidence.append(
            {
                "index": len(captures),
                "method": request.method,
                "url": str(request.url),
                "body": captures[-1],
                "raw_body_utf8": raw_body.decode("utf-8"),
                "body_bytes": len(raw_body),
                "body_sha256": hashlib.sha256(raw_body).hexdigest(),
            }
        )
        return httpx.Response(
            200,
            json=response_fixture(len(captures)),
            headers={"content-type": "application/json"},
            request=request,
        )

    transport = httpx.MockTransport(capture_handler)
    created_http_clients = []
    original_feature_client = feature_usage._FeatureUsageAsyncHttpxClient

    class OfflineFeatureClient(original_feature_client):
        def __init__(self, **kwargs):
            assert not any(
                key in kwargs for key in ("transport", "mounts", "proxy", "proxies")
            )
            kwargs.update(transport=transport, trust_env=False, follow_redirects=False)
            super().__init__(**kwargs)
            assert self._transport is transport
            assert not self._mounts
            assert self.event_hooks["request"]
            created_http_clients.append(self)

    monkeypatch.setattr(
        feature_usage, "_FeatureUsageAsyncHttpxClient", OfflineFeatureClient
    )
    # La configuración real selecciona el descriptor. El endpoint de la
    # instancia de prueba es deliberadamente .invalid; no contacta el sandbox.
    agents = production_factory.build_foundry_production_agents(
        FoundryProductionSettings(project_endpoint=_OFFLINE_ENDPOINT)
    )
    assert agents._allow_preview is True  # fábrica compartida intacta
    assert agents._credential is credential

    async def exercise():
        invocation = None
        try:
            loop = asyncio.get_running_loop()
            policy = asyncio.get_event_loop_policy()
            native_evidence["asyncio_harness"] = {
                "policy_type": type(policy).__module__ + "." + type(policy).__qualname__,
                "loop_type": type(loop).__module__ + "." + type(loop).__qualname__,
                "policy_configured_by_this_test": False,
            }
            invocation = await agents.begin_azure_operations(
                _PROMPT, agent_definition=definition
            )
            assert len(captures) == 1
            assert type(invocation.agent) is foundry_sdk.FoundryAgent
            assert invocation.agent.client.agent_name == definition.name
            assert invocation.agent.client.agent_version == definition.version
            assert invocation.agent.client.allow_preview is False
            sdk_client = invocation.agent.client.client
            assert sdk_client.max_retries == 2
            assert sdk_client.timeout == 120.0

            native = [
                content
                for message in invocation.response.messages
                for content in message.contents
                if content.type == "function_approval_request"
            ]
            assert len(native) == 1
            approval = native[0]
            assert isinstance(approval, Content)
            assert approval.user_input_request is True
            assert approval.id == _APPROVAL_ID
            assert approval.function_call.call_id == _APPROVAL_ID
            assert approval.function_call.name == authority.tool_name
            assert (
                approval.function_call.additional_properties["server_label"]
                == authority.server_label
            )
            assert json.loads(approval.function_call.arguments) == tool_arguments
            session_before = invocation.session
            assert session_before.service_session_id == _FIRST_RESPONSE_ID

            # Rechazo sintético, sin aprobación operacional ni MCP remoto.
            continued = await agents.continue_azure_operations(
                invocation=invocation,
                approval_request=approval,
                approved=False,
            )
            assert len(captures) == 2
            assert continued.agent is invocation.agent
            assert continued.session is session_before
            assert continued.owner_token is invocation.owner_token
            assert continued.session.service_session_id == _SECOND_RESPONSE_ID

            expected_reference = {
                "name": "agent-azure-operations-rg-list-sbx",
                "type": "agent_reference",
                "version": "1",
            }
            for body in captures:
                assert set(body) <= {
                    "input", "model", "previous_response_id", "store", "stream",
                    "max_tool_calls", "parallel_tool_calls", "agent_reference",
                }
                if "model" in body:
                    assert body["model"] == ""
                assert body["agent_reference"] == expected_reference
                assert type(body["max_tool_calls"]) is int
                assert body["max_tool_calls"] == 1
                assert body["parallel_tool_calls"] is False
                assert body["store"] is True
                assert body["stream"] is False
            first, second = captures
            assert first["input"] == [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": _PROMPT}],
                }
            ]
            assert "previous_response_id" not in first
            assert second["previous_response_id"] == _FIRST_RESPONSE_ID
            assert second["input"] == [
                {
                    "type": "mcp_approval_response",
                    "approval_request_id": _APPROVAL_ID,
                    "approve": False,
                }
            ]
            native_evidence.update(
                approval_type=type(approval).__module__ + "." + type(approval).__qualname__,
                approval_request_id=approval.id,
                tool_name=approval.function_call.name,
                server_label=approval.function_call.additional_properties["server_label"],
                arguments=tool_arguments,
                synthetic_decision=False,
                same_agent=continued.agent is invocation.agent,
                same_session=continued.session is session_before,
                same_owner=continued.owner_token is invocation.owner_token,
                session_response_id_before=_FIRST_RESPONSE_ID,
                session_response_id_after=continued.session.service_session_id,
                configured_sdk_max_retries=sdk_client.max_retries,
                configured_http_timeout_seconds=sdk_client.timeout,
            )
        finally:
            if invocation is not None:
                await invocation.agent.client.close()
            for client in created_http_clients:
                await client.aclose()

    # Solo plazo del harness local; no implementa el deadline del runner 2.7.
    async def bounded_exercise():
        await asyncio.wait_for(exercise(), timeout=20.0)

    asyncio.run(bounded_exercise())
    assert len(captures) == 2
    assert len(synthetic_attempts) == 2
    assert len(created_http_clients) == 1
    assert all(client.is_closed for client in created_http_clients)
    assert denied_attempts == []
    # JUnit conserva los cuerpos sintéticos realmente capturados en esta misma
    # ejecución. Nunca se incluyen headers, credenciales ni variables de entorno.
    request.node.user_properties.append(
        (
            "f27_b02_2_6_sdk_transport",
            json.dumps(
                {
                    "origin": "REAL_INSTALLED_SDK_SERIALIZED_TO_EXCLUSIVE_MOCK_TRANSPORT",
                    "sdk_versions_verified": _SDK_VERSIONS,
                    "python_version": ".".join(str(value) for value in sys.version_info[:3]),
                    "endpoint": _OFFLINE_ENDPOINT,
                    "os_header_metadata_is_synthetic": True,
                    "request_limit_scope": "PER_REQUEST_NOT_GLOBAL_WORKFLOW_BUDGET",
                    "service_selection_observed": False,
                    "requests": capture_evidence,
                    "native_continuation": native_evidence,
                    "synthetic_http_attempts": len(synthetic_attempts),
                    "denied_boundary_attempts": denied_attempts,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    )
