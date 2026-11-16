"""Composition of the independent worker, NOT the Teams/core HTTP host.

The deployment must supply a governor-owned job and qualified storage settings.
Do not expose this as a route taking pins, role flags, keys or evidence bodies
from callers. Creating a factory is not an Azure deployment or JWT proof.
"""
from __future__ import annotations

from src.agents.foundry_native_receipt_source import build_managed_identity_native_receipt_source
from src.azure_key_vault_receipt_signing import build_managed_identity_sign_attempt
from src.attestation.foundry_backend_attestor import AttestationJob, FoundryBackendAttestor
from src.persistence.azure_sql.attestation_journal import AzureSqlAttestationJournal
from src.persistence.azure_sql.connection_provider import build_mssql_python_connection_factory
from src.production_receipt_custody import build_receipt_custody_service


def build_independent_attestation_worker(*, job, sql_writer, sql_reader,
                                       account_url, container, policy, retain_until, clock):
    if type(job) is not AttestationJob:
        raise TypeError("Governor-owned AttestationJob required")
    if (sql_writer.managed_identity_client_id != job.attestor.managed_identity.client_id
            or job.attestor.managed_identity.kind != "user_assigned"):
        raise ValueError("Writer must use the explicitly pinned attestor UAMI")
    if sql_reader.managed_identity_client_id == job.backend.managed_identity.client_id:
        raise ValueError("Backend identity cannot be the custody reader")
    custody, close_custody = build_receipt_custody_service(scope=job.operation.trusted_scope,
        backend_keys=(job.backend.public_key,), attestor_keys=(job.attestor.public_key,),
        sql_writer=sql_writer, sql_reader=sql_reader, account_url=account_url, container=container,
        policy=policy, retain_until=retain_until)
    try:
        source = build_managed_identity_native_receipt_source(job.native)
    except Exception:
        close_custody()
        raise
    journal = AzureSqlAttestationJournal(
        connection_factory=build_mssql_python_connection_factory(sql_writer),
        read_connection_factory=build_mssql_python_connection_factory(sql_reader))
    worker = FoundryBackendAttestor(job=job, source=source, journal=journal,
        signer_factory=build_managed_identity_sign_attempt, custodian=custody, clock=clock)

    def close():
        try:
            source.close()
        finally:
            close_custody()
    return worker, close
