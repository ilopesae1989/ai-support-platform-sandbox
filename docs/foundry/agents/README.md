# Microsoft Foundry agent inventory

This directory contains a public, sanitized snapshot of the six Microsoft Foundry Prompt Agents used by AI Support Platform.

The source project endpoint, managed identity identifiers, MCP server addresses, connection identifiers, server labels and full system instructions are intentionally not stored because this repository is public.

The SHA256 values allow an authorized future LIVE read to verify whether an agent definition or its instructions changed.

The application runtime continues to use the explicit agent versions defined by `src/agents/catalog.py`. An endpoint selector such as `@latest` is recorded as inventory and does not replace that runtime authority.

| Agent key | Agent name | Effective | Latest published | Model | Tools |
| --- | --- | ---: | ---: | --- | ---: |
| classification | agent-classification-sbx | 7 | 7 | gpt-5-mini-sbx | 0 |
| knowledge | agent-knowledge-sbx | 8 | 8 | gpt-5-mini-sbx | 1 |
| alert_triage | agent-alert-triage-sbx | 10 | 10 | gpt-5-mini-sbx | 1 |
| procedure_execution | agent-procedure-execution-sbx | 6 | 6 | gpt-5-mini-sbx | 1 |
| azure_operations | agent-azure-operations-sbx | 13 | 13 | gpt-5-mini-sbx | 1 |
| itsm | agent-itsm-sbx | 6 | 6 | gpt-5-mini-sbx | 0 |

## Security policy

- Full system instructions: omitted; SHA256 retained.
- MCP/server URLs: omitted.
- Project connection IDs: omitted.
- Server labels: omitted.
- Managed identity and blueprint IDs: omitted.
- Hashes of private connection identifiers and endpoints: not published.
- Draft identifiers: not published; only presence/count is retained.
- Authorized tool names and approval surface: retained because they describe platform capability boundaries.

No file in this directory is runtime authority. Runtime routing, target selection, parameters, authorization, HITL, dispatch and replay protection remain governed by Python code.
