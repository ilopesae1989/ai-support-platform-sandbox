"""Factory assembly only: no token acquisition, SQL connection or Azure call."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

import pytest

from src.persistence.azure_blob_receipt_objects import LockedContainerPolicy

spec=importlib.util.spec_from_file_location("worker_fixture",Path(__file__).with_name("test_foundry_backend_attestor.py"))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def options():
    from src.persistence.azure_sql.connection_provider import AzureSqlManagedIdentitySettings
    f=fixture.setup()
    writer=AzureSqlManagedIdentitySettings("synthetic.database.windows.net","syntheticdb",
        f.job.attestor.managed_identity.client_id)
    reader=replace(writer,managed_identity_client_id="00000000-0000-0000-0000-000000000004")
    policy=LockedContainerPolicy("/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/synthetic"
        "/providers/Microsoft.Storage/storageAccounts/f27synthetic/blobServices/default"
        "/containers/receipts/immutabilityPolicies/default",'"etag"',2)
    return dict(job=f.job,sql_writer=writer,sql_reader=reader,account_url="https://f27synthetic.blob.core.windows.net",
        container="receipts",policy=policy,retain_until=datetime.now(timezone.utc)+timedelta(days=1),
        clock=lambda:"2026-10-28T10:00:04Z")


def test_factory_creates_explicit_identity_worker_without_io():
    from src.production_attestation import build_independent_attestation_worker
    kw=options();worker,close=build_independent_attestation_worker(**kw)
    assert worker.job==kw["job"] and worker.source.pin.identity==kw["job"].attestor.managed_identity
    assert worker.job.owner not in repr(worker)
    close()


@pytest.mark.parametrize("fault",["writer","reader_equals_writer","reader_backend","target","missing_reader"])
def test_bad_identity_or_storage_target_is_rejected_before_worker_creation(fault):
    from src.production_attestation import build_independent_attestation_worker
    kw=options()
    if fault=="writer":kw["sql_writer"]=replace(kw["sql_writer"],managed_identity_client_id="00000000-0000-0000-0000-000000000009")
    elif fault=="reader_equals_writer":kw["sql_reader"]=kw["sql_writer"]
    elif fault=="reader_backend":
        kw["job"]=replace(kw["job"],backend=replace(kw["job"].backend,managed_identity=
            fixture.ReceiptManagedIdentity("user_assigned","00000000-0000-0000-0000-000000000008",
                                          kw["sql_reader"].managed_identity_client_id)))
    elif fault=="target":kw["sql_reader"]=replace(kw["sql_reader"],database="otherdb")
    else:kw["sql_reader"]=replace(kw["sql_reader"],managed_identity_client_id=None)
    with pytest.raises((ValueError,TypeError)):build_independent_attestation_worker(**kw)
