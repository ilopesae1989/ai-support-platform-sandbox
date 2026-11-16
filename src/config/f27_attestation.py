"""Deployment-owned, digest-pinned configuration for the independent receipt path."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

from src.azure_key_vault_receipt_signing import KeyVaultReceiptPin, ReceiptManagedIdentity, validate_independent_receipt_pins
from src.attestation.foundry_backend_attestor import KINDS, LINK_DOMAIN
from src.attestation.governor_outbox import AzureSqlGovernorOutbox, GovernorAttestationPublisher
from src.persistence.azure_sql.connection_provider import AzureSqlManagedIdentitySettings, build_mssql_python_connection_factory
from src.workflows.incident_resolution.mcp_receipt_trust import TrustedPublicKey


def load_attestation_configuration(environment):
    enabled = environment.get("F27_ATTESTATION_ENABLED")
    if enabled is None or enabled == "false":
        return None
    if enabled != "true":
        raise ValueError("Explicit F27 activation flag required")
    path, digest = environment.get("F27_ATTESTATION_CONFIG_PATH"), environment.get("F27_ATTESTATION_CONFIG_SHA256")
    if not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Exact deployment-owned configuration file and SHA256 required")
    raw = Path(path).read_bytes()
    if not 0 < len(raw) <= 65536 or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Attestation configuration digest mismatch")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("Duplicate deployment setting")
            result[key] = value
        return result
    cfg = json.loads(raw, object_pairs_hook=unique)
    if set(cfg) != {"schema", "scope", "project_endpoint", "keys", "deployments", "sql", "blob"} or cfg["schema"] != "f27-runtime-attestation-v1":
        raise ValueError("Exact runtime attestation configuration required")
    if set(cfg["keys"]) != {"group_list", "compute_vm_power-state", "attestor"}:
        raise ValueError("Exact three-key registry required")
    pins = {}
    for label, value in cfg["keys"].items():
        if set(value) != {"key_id", "identity", "public_spki_base64", "spki_sha256"}:
            raise ValueError("Exact public key pin required")
        public = base64.b64decode(value["public_spki_base64"], validate=True)
        if hashlib.sha256(public).hexdigest() != value["spki_sha256"]:
            raise ValueError("SPKI fingerprint mismatch")
        issuer, domains = (("correlation_attestor", frozenset({LINK_DOMAIN})) if label == "attestor"
            else ("mcp_backend", frozenset("event:" + k for k in KINDS)))
        pins[label] = KeyVaultReceiptPin(value["key_id"], ReceiptManagedIdentity(**value["identity"]),
            cfg["scope"], TrustedPublicKey(issuer, public, domains))
    for label in ("group_list", "compute_vm_power-state"):
        validate_independent_receipt_pins(pins[label], pins["attestor"])
        d = cfg["deployments"][label]
        if (set(d) != {"revision", "image", "agent_name", "agent_version", "server_label"}
                or not re.fullmatch(r"[a-z0-9-]{1,200}", d["revision"])
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", d["image"])
                or not re.fullmatch(r"[1-9][0-9]*", d["agent_version"])):
            raise ValueError("Exact qualified deployment pin required")
    if len({p.public_key.kid for p in pins.values()}) != 3 or len({p.managed_identity.principal_id for p in pins.values()}) != 3:
        raise ValueError("Three independent receipt principals and keys required")
    sql = cfg["sql"]
    if set(sql) != {"server", "database", "core_writer_client_id", "attestor_writer_client_id", "custody_reader_client_id"}:
        raise ValueError("Exact SQL identity boundary required")
    sql_ids = [str(UUID(sql[label + "_client_id"])) for label in ("core_writer", "attestor_writer", "custody_reader")]
    if len(set(sql_ids)) != 3 or sql_ids[1] != pins["attestor"].managed_identity.client_id:
        raise ValueError("Separate core, attestor and custody reader SQL identities required")
    if set(cfg["deployments"]) != {"group_list", "compute_vm_power-state"}:
        raise ValueError("Exact deployment registry required")
    cfg["pins"] = pins
    return cfg


def sql_settings(cfg, role):
    values = cfg["sql"]
    return AzureSqlManagedIdentitySettings(values["server"], values["database"], values[role + "_client_id"])


def build_governor_attestation_publisher(environment):
    cfg = load_attestation_configuration(environment)
    if cfg is None:
        return None
    key = base64.b64decode(environment.get("F27_FINGERPRINT_KEY", ""), validate=True)
    writer = sql_settings(cfg, "core_writer")
    if writer.managed_identity_client_id != environment.get("AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"):
        raise ValueError("Outbox writer must be the served core SQL identity")
    factory = build_mssql_python_connection_factory(writer)
    outbox = AzureSqlGovernorOutbox(read_factory=factory, write_factory=factory)
    return GovernorAttestationPublisher(outbox=outbox, project_endpoint=cfg["project_endpoint"],
        backend_pins={k: cfg["pins"][k] for k in ("group_list", "compute_vm_power-state")}, attestor_pin=cfg["pins"]["attestor"],
        deployment_pins=cfg["deployments"], fingerprint_key=key)
