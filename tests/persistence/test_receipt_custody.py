"""Real ES256 verification + injected storage failures, no Azure or SQL engine."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json

import pytest

from src.persistence.receipt_custody import ReceiptCustodian, CustodyOutcome, IndexOutcome, sha256
from src.persistence.azure_sql.receipt_custody_index import AzureSqlReceiptCustodyIndex
from src.persistence.azure_blob_receipt_objects import (
    AzureBlobReceiptObjects, LockedContainerPolicy, SinglePutTransport,
)

# Reuse the established cryptographic fixtures; never mock signature acceptance.
spec = importlib.util.spec_from_file_location("custody_crypto_fixture", Path(__file__).parents[1] /
    "workflows/incident_resolution/test_mcp_authenticated_backend_bridge.py")
crypto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crypto)

ACCOUNT = "https://f27synthetic.blob.core.windows.net"
CONTAINER = "closed-receipts"
POLICY_ID = ("/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-f27"
             "/providers/Microsoft.Storage/storageAccounts/f27synthetic/blobServices/default"
             "/containers/closed-receipts/immutabilityPolicies/default")


class Objects:
    def __init__(self):
        self.rows = {}
        self.puts = []
        self.reads = []
        self.fail_at = None
        self.corrupt = False

    def create_and_verify(self, name, data):
        self.puts.append(name)
        if name in self.rows:
            raise RuntimeError("Existing object is uncertain, not auto-retried")
        self.rows[name] = data
        if len(self.puts) == self.fail_at:
            raise ConnectionError("Response lost after write")
        return self.read_and_verify(name, data)

    def read_and_verify(self, name, data):
        self.reads.append(name)
        if self.rows[name] != data or self.corrupt:
            raise ValueError("Readback changed")
        return dict(name=name, sha256=sha256(data), uri=ACCOUNT + "/" + CONTAINER + "/" + name,
                    etag='"stable"', policy_id=POLICY_ID, policy_state="Locked")


class DB:
    def __init__(self):
        self.rows = {}
        self.executions = []
        self.connections = []
        self.fail_insert = False
        self.fail_read = False
        self.commit_mode = "success"
        self.autocommit = False

    def connect(self):
        c = Connection(self)
        self.connections.append(c)
        return c


class Connection:
    def __init__(self, db):
        self.db, self.autocommit, self.pending = db, db.autocommit, None
        self.closed = False
        self.commits = self.rollbacks = 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1
        if self.db.commit_mode == "before":
            raise ConnectionError("Unknown commit")
        key, row = self.pending
        self.db.rows[key] = row
        self.pending = None
        if self.db.commit_mode == "after":
            raise ConnectionError("Acknowledgement lost")

    def rollback(self):
        self.rollbacks += 1
        self.pending = None

    def close(self):
        self.closed = True


class Cursor:
    def __init__(self, conn):
        self.conn, self.rows = conn, []

    def execute(self, sql, p):
        db = self.conn.db
        db.executions.append((sql, p))
        assert not any(word in sql.upper() for word in ("UPDATE ", "DELETE ", "MERGE ", "CREATE "))
        if sql.startswith("INSERT"):
            if db.fail_insert or p["logical"] in db.rows:
                raise RuntimeError("Unclassified insert error")
            self.conn.pending = (p["logical"], (p["digest"], p["record"]))
        else:
            if db.fail_read:
                raise ConnectionError("Read unavailable")
            self.rows = [db.rows[p["logical"]]] if p["logical"] in db.rows else []

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        pass


def bundle(**kwargs):
    f = crypto._fixture(**kwargs)
    objects, db = Objects(), DB()
    custodian = ReceiptCustodian(objects=objects, index=AzureSqlReceiptCustodyIndex(
        connection_factory=db.connect, read_connection_factory=db.connect),
        bridge_verifier=f["bridge_verifier"], backend_verifier=f["backend_verifier"])
    inputs = {k: f[k] for k in ("pinned", "signed_bridge", "backend_event")}
    return custodian, inputs, objects, db


@pytest.mark.parametrize("state,human", [("PENDING", None), ("DENIED", None), ("APPROVED", "human-01")])
def test_complete_pair_persisted_and_read_back_never_grants_authority(state, human):
    custodian, inputs, objects, db = bundle(state=state, human=human)
    result = custodian.store(**inputs)
    assert result.outcome == CustodyOutcome.STORED_VERIFIED_NO_AUTHORITY
    assert result.object_create_attempts == 2 and result.index_insert_attempts == 1
    assert len(db.connections) == 2 and all(c.closed for c in db.connections)
    assert db.connections[0] is not db.connections[1]
    record = json.loads(next(iter(db.rows.values()))[1])
    assert record["approval_state"] == state
    assert record["backend_kid"] != record["attestor_kid"]
    assert record["response_id"] == inputs["pinned"].response_id
    assert {json.loads(raw)["source_receipt"]["issuer"] for raw in objects.rows.values()} == {
        "mcp_backend", "correlation_attestor"}
    before = len(db.executions)
    recovered = custodian.reconcile(**inputs)
    assert recovered.outcome == CustodyOutcome.PRESENT_VERIFIED_NO_AUTHORITY
    assert recovered.record_sha256 == result.record_sha256
    assert recovered.object_create_attempts == recovered.index_insert_attempts == 0
    assert len(objects.puts) == 2 and len(db.executions) == before + 1


@pytest.mark.parametrize("target,field,value", [
    ("backend_event", "event_id", "other"),
    ("signed_bridge", "linked_response_id", "wrong"),
    ("signed_bridge", "technical_approval", True),
    ("backend_event", "Authorization", "Bearer forbidden"),
    ("backend_event", "source_receipt", {"issuer": "mcp_backend", "proof_id": "forged"}),
])
def test_tampered_pair_rejected_before_io(target, field, value):
    custodian, inputs, objects, db = bundle()
    inputs[target][field] = value
    assert custodian.store(**inputs).outcome == CustodyOutcome.REJECTED_BEFORE_IO
    assert not objects.puts and not objects.reads and not db.connections


@pytest.mark.parametrize("field,value", [("trusted_scope", "tenant:another/f27"),
                                        ("operation_id", "different-operation"),
                                        ("agent_version", "999")])
def test_cross_scope_and_operation_rejected_before_io(field, value):
    custodian, inputs, objects, db = bundle()
    inputs["pinned"] = replace(inputs["pinned"], **{field: value})
    assert custodian.store(**inputs).outcome == CustodyOutcome.REJECTED_BEFORE_IO
    assert not objects.puts and not db.connections


@pytest.mark.parametrize("failed_object", [1, 2])
def test_partial_worm_failure_preserves_objects_and_never_inserts(failed_object):
    custodian, inputs, objects, db = bundle()
    objects.fail_at = failed_object
    result = custodian.store(**inputs)
    assert result.outcome == CustodyOutcome.STORAGE_UNCERTAIN_NO_RETRY
    assert len(objects.rows) == len(objects.puts) == failed_object
    assert not db.connections
    recovered = custodian.reconcile(**inputs)
    assert recovered.outcome != CustodyOutcome.PRESENT_VERIFIED_NO_AUTHORITY
    assert len(objects.puts) == failed_object
    assert not any(sql.startswith("INSERT") for sql, p in db.executions)


@pytest.mark.parametrize("mode,expected", [("before", CustodyOutcome.INDEX_UNCERTAIN_NO_RETRY),
                                          ("after", CustodyOutcome.PRESENT_VERIFIED_NO_AUTHORITY)])
def test_commit_unknown_requires_read_only_reconciliation(mode, expected):
    custodian, inputs, objects, db = bundle()
    db.commit_mode = mode
    result = custodian.store(**inputs)
    assert result.outcome == CustodyOutcome.INDEX_UNCERTAIN_NO_RETRY
    assert len(db.executions) == 1 and db.connections[0].rollbacks == 0
    assert custodian.reconcile(**inputs).outcome == expected
    assert len(objects.puts) == 2
    assert sum(sql.startswith("INSERT") for sql, p in db.executions) == 1


@pytest.mark.parametrize("fault", ["autocommit", "fail_insert", "fail_read"])
def test_sql_failure_never_certifies_or_retries(fault):
    custodian, inputs, objects, db = bundle()
    setattr(db, fault, True)
    result = custodian.store(**inputs)
    assert result.outcome == CustodyOutcome.INDEX_UNCERTAIN_NO_RETRY
    assert len(objects.puts) == 2
    assert sum(sql.startswith("INSERT") for sql, p in db.executions) <= 1
    assert all(c.closed for c in db.connections)


def test_replay_is_not_dispatch_and_does_not_overwrite():
    custodian, inputs, objects, db = bundle()
    assert custodian.store(**inputs).outcome == CustodyOutcome.STORED_VERIFIED_NO_AUTHORITY
    result = custodian.store(**inputs)
    assert result.outcome == CustodyOutcome.STORAGE_UNCERTAIN_NO_RETRY
    assert len(objects.rows) == 2 and len(db.rows) == 1
    assert sum(sql.startswith("INSERT") for sql, p in db.executions) == 1


def test_conflicting_index_and_modified_blob_fail_closed():
    custodian, inputs, objects, db = bundle()
    custodian.store(**inputs)
    key = next(iter(db.rows))
    db.rows[key] = (b"x" * 32, b"different")
    assert custodian.reconcile(**inputs).outcome == CustodyOutcome.CONFLICT_NO_AUTHORITY
    objects.corrupt = True
    assert custodian.reconcile(**inputs).outcome == CustodyOutcome.STORAGE_UNCERTAIN_NO_RETRY


def blob_bundle():
    data = b'{"receipt":"synthetic"}'
    name = "v1/" + "a" * 64 + "/backend-" + sha256(data) + ".json"
    policy = LockedContainerPolicy(POLICY_ID, '"policy-etag"', 2)
    snapshot = {"id": POLICY_ID, "etag": policy.etag, "properties": {
        "state": "Locked", "immutabilityPeriodSinceCreationInDays": 2,
        "allowProtectedAppendWrites": False, "allowProtectedAppendWritesAll": False}}
    properties = SimpleNamespace(etag='"etag"', creation_time=datetime.now(timezone.utc),
                                 size=len(data), blob_type="BlockBlob")
    calls = []
    class Blob:
        def upload_blob(self, raw, **kwargs):
            calls.append(("put", raw, kwargs))
        def get_blob_properties(self, **kwargs):
            calls.append(("head",))
            return properties
        def download_blob(self, **kwargs):
            calls.append(("get", kwargs))
            return SimpleNamespace(readall=lambda: data)
    class Container:
        def get_blob_client(self, n):
            assert n == name
            return Blob()
    objects = AzureBlobReceiptObjects(account_url=ACCOUNT, container=CONTAINER,
        writer=Container(), reader=Container(), policy_reader=lambda: snapshot,
        policy=policy, retain_until=datetime.now(timezone.utc) + timedelta(days=1))
    return objects, name, data, snapshot, properties, calls


def test_blob_uses_closed_object_conditional_creation_and_independent_read():
    objects, name, data, snapshot, properties, calls = blob_bundle()
    location = objects.create_and_verify(name, data)
    assert location["uri"] == ACCOUNT + "/" + CONTAINER + "/" + name
    assert location["policy_state"] == "Locked" and location["sha256"] == sha256(data)
    assert calls[0][2]["blob_type"] == "BlockBlob" and calls[0][2]["overwrite"] is False
    get = [c for c in calls if c[0] == "get"][0][1]
    assert get["etag"] == properties.etag and get["length"] == len(data)
    assert [c[0] for c in calls] == ["put", "head", "get", "head"]


@pytest.mark.parametrize("field,value", [("state", "Unlocked"),
    ("allowProtectedAppendWrites", True), ("allowProtectedAppendWritesAll", True),
    ("immutabilityPeriodSinceCreationInDays", 3), ("immutabilityPeriodSinceCreationInDays", True)])
def test_policy_drift_prevents_any_put(field, value):
    objects, name, data, snapshot, properties, calls = blob_bundle()
    snapshot["properties"][field] = value
    with pytest.raises(ValueError):
        objects.create_and_verify(name, data)
    assert calls == []


@pytest.mark.parametrize("attribute,value", [("blob_type", "AppendBlob"), ("size", 0),
    ("etag", ""), ("creation_time", datetime.now(timezone.utc) - timedelta(days=5))])
def test_wrong_blob_or_insufficient_retention_rejected(attribute, value):
    objects, name, data, snapshot, properties, calls = blob_bundle()
    setattr(properties, attribute, value)
    with pytest.raises(ValueError):
        objects.read_and_verify(name, data)
    assert not any(c[0] == "put" for c in calls)


def test_single_put_guard_prevents_replay_even_after_transport_failure(monkeypatch):
    from azure.core.pipeline.transport import RequestsTransport
    from azure.core.pipeline.transport import HttpRequest
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise ConnectionError("Simulated lost response")
    monkeypatch.setattr(RequestsTransport, "send", fail)
    transport = SinglePutTransport(account_url=ACCOUNT, container=CONTAINER)
    name = "v1/" + "a" * 64 + "/backend-" + "b" * 64 + ".json"
    request = HttpRequest("PUT", ACCOUNT + "/" + CONTAINER + "/" + name,
                          headers={"x-ms-blob-type": "BlockBlob", "If-None-Match": "*"})
    with pytest.raises(ConnectionError):
        transport.send(request)
    with pytest.raises(RuntimeError):
        transport.send(request)
    assert calls == [1]


@pytest.mark.parametrize("method,query,blob_type,conditional", [
    ("DELETE", "", "BlockBlob", "*"), ("PUT", "?comp=appendblock", "BlockBlob", "*"),
    ("PUT", "", "AppendBlob", "*"), ("PUT", "", "BlockBlob", "")])
def test_write_transport_rejects_delete_append_and_unconditional_put(method, query, blob_type, conditional):
    from azure.core.pipeline.transport import HttpRequest
    transport = SinglePutTransport(account_url=ACCOUNT, container=CONTAINER)
    name = "v1/" + "a" * 64 + "/backend-" + "b" * 64 + ".json"
    request = HttpRequest(method, ACCOUNT + "/" + CONTAINER + "/" + name + query,
                          headers={"x-ms-blob-type": blob_type, "If-None-Match": conditional})
    with pytest.raises(ValueError):
        transport.send(request)


def test_real_blob_sdk_emits_conditional_single_put_without_network(monkeypatch):
    from azure.storage.blob import ContainerClient
    from azure.core.pipeline.transport import RequestsTransport, HttpResponse
    requests = []
    class Response(HttpResponse):
        def __init__(self, request):
            super().__init__(request, None)
            self.status_code = 201
            self.headers = {"etag": '"created"', "last-modified": "Wed, 11 Nov 2026 10:00:00 GMT"}
        def body(self):
            return b""
    def sent(self, request, **kwargs):
        requests.append(request)
        return Response(request)
    monkeypatch.setattr(RequestsTransport, "send", sent)
    transport = SinglePutTransport(account_url=ACCOUNT, container=CONTAINER)
    client = ContainerClient(ACCOUNT, CONTAINER, credential=None, transport=transport,
                             retry_total=0, max_single_put_size=65536)
    data = b"bounded synthetic receipt"
    name = "v1/" + "a" * 64 + "/backend-" + sha256(data) + ".json"
    client.get_blob_client(name).upload_blob(data, blob_type="BlockBlob", length=len(data),
                                            overwrite=False, max_concurrency=1)
    assert len(requests) == 1 and requests[0].headers["If-None-Match"] == "*"
    assert requests[0].headers["x-ms-blob-type"] == "BlockBlob"
    assert requests[0].body == data
    client.close()


@pytest.mark.parametrize("fault", ["same_identity", "different_database", "no_reader_identity", "same_key"])
def test_composition_rejects_unqualified_boundaries_before_clients(monkeypatch, fault):
    import src.production_receipt_custody as composition
    from src.persistence.azure_sql.connection_provider import AzureSqlManagedIdentitySettings as Settings
    f = crypto._fixture()
    writer = Settings("synthetic.database.windows.net", "f27", "00000000-0000-0000-0000-000000000001")
    reader = Settings("synthetic.database.windows.net", "f27", "00000000-0000-0000-0000-000000000002")
    backend_keys = [f["backend_public"]]
    attestor_keys = [f["attestor_public"]]
    if fault == "same_identity": reader = writer
    if fault == "different_database": reader = replace(reader, database="other")
    if fault == "no_reader_identity": reader = replace(reader, managed_identity_client_id=None)
    if fault == "same_key": attestor_keys = backend_keys
    created = []
    monkeypatch.setattr(composition, "build_managed_identity_receipt_objects", lambda **kw: created.append(kw))
    with pytest.raises((ValueError, TypeError)):
        composition.build_receipt_custody_service(scope=crypto.SCOPE, backend_keys=backend_keys,
            attestor_keys=attestor_keys, sql_writer=writer, sql_reader=reader, account_url=ACCOUNT,
            container=CONTAINER, policy=LockedContainerPolicy(POLICY_ID, '"etag"', 2),
            retain_until=datetime.now(timezone.utc) + timedelta(days=1))
    assert not created


def test_composition_constructs_no_io_and_consumes_key_generators_once(monkeypatch):
    import src.production_receipt_custody as composition
    from src.persistence.azure_sql.connection_provider import AzureSqlManagedIdentitySettings as Settings
    f = crypto._fixture()
    writer = Settings("synthetic.database.windows.net", "f27", "00000000-0000-0000-0000-000000000001")
    reader = replace(writer, managed_identity_client_id="00000000-0000-0000-0000-000000000002")
    called = []
    def objects(**kw):
        called.append(kw)
        return Objects(), lambda: None
    monkeypatch.setattr(composition, "build_managed_identity_receipt_objects", objects)
    service, close = composition.build_receipt_custody_service(scope=crypto.SCOPE,
        backend_keys=(x for x in [f["backend_public"]]), attestor_keys=(x for x in [f["attestor_public"]]),
        sql_writer=writer, sql_reader=reader, account_url=ACCOUNT, container=CONTAINER,
        policy=LockedContainerPolicy(POLICY_ID, '"etag"', 2),
        retain_until=datetime.now(timezone.utc) + timedelta(days=1))
    assert isinstance(service, ReceiptCustodian) and callable(close)
    assert called[0]["writer_client_id"] != called[0]["verifier_client_id"]


def test_input_mutation_after_verification_cannot_change_stored_signed_bytes():
    custodian, inputs, objects, db = bundle()
    original = deepcopy(inputs["backend_event"])
    real_create = objects.create_and_verify
    def change_input(name, data):
        inputs["backend_event"]["event_id"] = "mutated-after-snapshot"
        return real_create(name, data)
    objects.create_and_verify = change_input
    assert custodian.store(**inputs).outcome == CustodyOutcome.STORED_VERIFIED_NO_AUTHORITY
    stored = [json.loads(data) for name, data in objects.rows.items() if "/backend-" in name][0]
    assert stored == original


def test_pinned_appendblob_permission_preserves_closed_blockblob_custody():
    objects, name, data, snapshot, properties, calls = blob_bundle()
    objects._policy = replace(objects._policy, allow_protected_append_writes=True)
    snapshot["properties"]["allowProtectedAppendWrites"] = True
    result = objects.create_and_verify(name, data)
    assert result["policy_append_blobs_allowed"] is True
    assert result["policy_append_all_allowed"] is False
    assert result["policy_state"] == "Locked"
    assert calls[0][2]["blob_type"] == "BlockBlob" and calls[0][2]["overwrite"] is False


@pytest.mark.parametrize("value", [True, None, "false", 0, 1])
def test_append_all_unknown_or_enabled_rejected_even_with_appendblob_pin(value):
    objects, name, data, snapshot, properties, calls = blob_bundle()
    objects._policy = replace(objects._policy, allow_protected_append_writes=True)
    snapshot["properties"].update(allowProtectedAppendWrites=True, allowProtectedAppendWritesAll=value)
    with pytest.raises(ValueError):
        objects.create_and_verify(name, data)
    assert calls == []


@pytest.mark.parametrize("value", [None, 1, "false"])
def test_appendblob_policy_pin_requires_exact_boolean(value):
    with pytest.raises(ValueError):
        LockedContainerPolicy(POLICY_ID, '"etag"', 1, allow_protected_append_writes=value)
