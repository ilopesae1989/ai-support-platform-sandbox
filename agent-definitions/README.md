# Agent definitions

This directory contains the source-controlled desired configuration for the Microsoft Foundry Prompt Agents used by AI Support Platform.

Unlike `docs/foundry/agents/`, which remains a sanitized evidence snapshot, this directory intentionally stores the full system instructions for each explicitly versioned agent.

## Authority model

- `src/agents/catalog.py` governs the agent name and runtime version selected by the application.
- `agent-definitions/` records the desired source-controlled system instructions for those versions.
- Microsoft Foundry Agent Service is the deployed LIVE authority.
- SHA-256 is used to detect drift between source-controlled instructions and LIVE instructions.
- Python code remains authoritative for routing, authorization, HITL, target identity, operation identity, dispatch, replay protection, workflow transitions and durable state.

## Security

This repository is public.

Do not store credentials, access tokens, SAS values, passwords, private endpoints, connection identifiers, managed identity identifiers, private keys or other secrets in this directory.

Agent instructions must never become operational authority merely because they are source controlled.
