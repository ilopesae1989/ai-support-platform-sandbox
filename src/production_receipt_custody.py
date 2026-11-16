"""Explicit custody composition, not yet attached to the served Teams workflow.

Construction performs no remote calls. No defaults discover or provision keys,
identities, storage or schema. Integration into the governor requires a qualified
producer/attestor ingress; this factory does not fabricate that boundary.
"""
from __future__ import annotations

from src.persistence.azure_blob_receipt_objects import build_managed_identity_receipt_objects
from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings, build_mssql_python_connection_factory,
)
from src.persistence.azure_sql.receipt_custody_index import AzureSqlReceiptCustodyIndex
from src.persistence.receipt_custody import ReceiptCustodian
from src.workflows.incident_resolution.mcp_receipt_trust import IndependentReceiptVerifier


def build_receipt_custody_service(*, scope, backend_keys, attestor_keys,
                                 sql_writer: AzureSqlManagedIdentitySettings,
                                 sql_reader: AzureSqlManagedIdentitySettings,
                                 account_url, container, policy, retain_until):
    if (type(sql_writer) is not AzureSqlManagedIdentitySettings
            or type(sql_reader) is not AzureSqlManagedIdentitySettings):
        raise TypeError("Explicit SQL settings required")
    if ((sql_writer.server, sql_writer.database) != (sql_reader.server, sql_reader.database)
            or sql_writer.managed_identity_client_id is None
            or sql_reader.managed_identity_client_id is None
            or sql_writer.managed_identity_client_id.lower() == sql_reader.managed_identity_client_id.lower()):
        raise ValueError("Same SQL target and separate explicit identities required")
    backend_keys, attestor_keys = tuple(backend_keys), tuple(attestor_keys)
    backend = IndependentReceiptVerifier(scope=scope, keys=backend_keys)
    bridge = IndependentReceiptVerifier(scope=scope, keys=attestor_keys)
    if not backend_keys or not attestor_keys:
        raise ValueError("Both pinned public key registries required")
    if ({key.kid for key in backend_keys} & {key.kid for key in attestor_keys}
            or any(key.issuer != "mcp_backend" for key in backend_keys)
            or any(key.issuer != "correlation_attestor" for key in attestor_keys)):
        raise ValueError("Separate trusted issuers and keys required")
    index = AzureSqlReceiptCustodyIndex(
        connection_factory=build_mssql_python_connection_factory(sql_writer),
        read_connection_factory=build_mssql_python_connection_factory(sql_reader))
    objects, close = build_managed_identity_receipt_objects(
        account_url=account_url, container=container, policy=policy,
        writer_client_id=sql_writer.managed_identity_client_id,
        verifier_client_id=sql_reader.managed_identity_client_id,
        retain_until=retain_until)
    return ReceiptCustodian(objects=objects, index=index,
                            bridge_verifier=bridge, backend_verifier=backend), close
