"""Offline inventory contract on real SQLite and MAF file checkpoints."""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import sqlite3
from uuid import UUID

import pytest

from src.persistence.execution_inventory import sqlite_inventory_page, sqlite_store_residuals
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.review.execution_inventory import main, write_inventory_report
from src.runtime.execution_affinity import AFFINITY_STATE_KEY
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY
from tests.runtime.test_incident_execution_queue import CODEC, affinity, prepare, snapshot, stores
from tests.workflows.incident_resolution.test_admitted_execution_checkpoint import pending, setup, worker


def observe(tmp_path, consumer=None, **kwargs):
    return sqlite_inventory_page(database=tmp_path / "state.db", checkpoints=tmp_path / "checkpoints",
                                 consumer=consumer or affinity(), **kwargs)


def sources(tmp_path):
    (tmp_path / "checkpoints").mkdir()
    return stores(tmp_path)


def document(checkpoint="leaf", parent="entry", *, execution="wf-one", status="running", messages=None, requests=None):
    return dict(workflow_name="incident-resolution", version="1.0", checkpoint_id=checkpoint,
                previous_checkpoint_id=parent, graph_signature_hash="a" * 64,
                messages=messages or {}, pending_request_info_events=requests or {},
                state={EXECUTION_ID_STATE_KEY: execution, AFFINITY_STATE_KEY: affinity().to_document(),
                       "procedure_runtime_state": {"workflow_id": execution, "workflow_status": status}})


def write_cp(tmp_path, doc, filename=None):
    path = tmp_path / "checkpoints" / ((filename or doc["checkpoint_id"]) + ".json")
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def enter(tmp_path):
    queue, _, _ = sources(tmp_path)
    queue.admit(execution_id="wf-one", input_sha256="d"*64)
    marker = f"internal:classification-affinity-{affinity().fingerprint}-admitted-v1"
    root = document("entry", None, messages={marker: ["opaque"]})
    root["state"] = {}
    write_cp(tmp_path, root)
    return queue


@pytest.mark.asyncio
async def test_native_admission_hitl_claim_and_terminal_rejection_are_observable_after_reopen(tmp_path):
    state = setup(tmp_path)
    args = dict(database=state.path, checkpoints=tmp_path / "checkpoints", consumer=state.case.affinity)
    first, = sqlite_inventory_page(**args)["executions"]
    assert first["observed_state"] == "start_unconfirmed"
    request, _ = await pending(state)
    before = snapshot(state.path)
    row, = sqlite_inventory_page(**args)["executions"]
    assert row["observed_state"] == "hitl_checkpoint" and row["issues"] == []
    assert row["approvals"] == {"pending": 1} and row["candidate_jobs"] == {"pending": 1}
    report = sqlite_inventory_page(**args)
    assert report["page_drain_blockers"] == [{"execution_id": row["execution_id"], "reasons": [
        "hitl_checkpoint", "approval_unfinished", "continuation_unfinished"]}]
    assert snapshot(state.path) == before
    active, _ = worker(state)
    assert (await active.process_next_once()).value == "completed"
    before = snapshot(state.path)
    done, = sqlite_inventory_page(**args)["executions"]
    assert done["observed_state"] == "terminal_checkpoint" and done["checkpoint_count"] > row["checkpoint_count"]
    assert done["candidate_jobs"] == {"completed": 1} and done["approvals"] == {"completed": 1}
    assert before == snapshot(state.path)
    assert first["rejection_receipt"] == {"status": "absent"}
    assert done["rejection_receipt"] == {
        "status": "recorded", "notification_delivery": "unconfirmed",
        "approval_sha256": hashlib.sha256(request.data.approval_id.encode()).hexdigest(),
    }
    assert sqlite_inventory_page(**args)["page_drain_blockers"] == [{
        "execution_id": done["execution_id"], "reasons": ["notification_delivery_unconfirmed"]}]
    assert request.data.approval_id not in json.dumps(done)


def test_foreign_release_visible_within_installation_and_claim_is_untouched(tmp_path):
    queue, approvals, path = sources(tmp_path)
    prepare(queue, approvals)
    claim = queue.claim_next(worker_id="operator-secret")
    previous = snapshot(path)
    consumer = replace(affinity(), foundry_sha256="e"*64)
    row, = observe(tmp_path, consumer)["executions"]
    assert row["compatible"] is False and row["candidate_jobs"] == {"claimed": 1}
    assert row["observed_state"] == "unresolved" and "approval_checkpoint_unconfirmed" in row["issues"]
    assert (queue.get(claim.approval_id).claimed_by, queue.get(claim.approval_id).attempt_count) == ("operator-secret", 1)
    assert "operator-secret" not in json.dumps(row) and snapshot(path) == previous


def test_installation_scope_precedes_pagination_and_foreign_data_stays_private(tmp_path):
    queue, _, _ = sources(tmp_path)
    for key in ("wf-c", "wf-a", "wf-b"):
        queue.admit(execution_id=key, input_sha256="a"*64)
    other, approvals, _ = stores(tmp_path, replace(affinity(), installation_id="A"))
    prepare(other, approvals, "B-sensitive")
    first = observe(tmp_path, limit=2)
    second = observe(tmp_path, limit=2, after=first["next_after"])
    assert first["next_after"] == "wf-b" and second["next_after"] is None
    assert [row["execution_id"] for row in first["executions"] + second["executions"]] == ["wf-a", "wf-b", "wf-c"]
    assert "sensitive" not in json.dumps(first) + json.dumps(second)
    assert "whole_store" not in json.dumps(first)
    assert observe(tmp_path, after="wf-z")["executions"] == []


@pytest.mark.parametrize("options", [{"limit": True}, {"limit": 0}, {"limit": 101}, {"after": "../bad"}])
def test_invalid_pagination_is_rejected(tmp_path, options):
    sources(tmp_path)
    with pytest.raises(ValueError):
        observe(tmp_path, **options)


@pytest.mark.parametrize(("status", "messages", "requests", "phase"), [
    ("waiting_human", {}, {"pending-human": None}, "hitl_registration_unconfirmed"),
    ("running", {}, {"unknown": None}, "pending_request_unidentified"),
    ("waiting_validation", {}, {"rchk-" + str(UUID(int=1)): None}, "wait_checkpoint"),
    ("running", {}, {"rchk-" + str(UUID(int=1)): None}, "pending_request_unidentified"),
    ("running", {}, {"rchk-bad": None}, "pending_request_unidentified"),
    ("running", {"next": ["opaque"]}, {}, "in_progress"),
    ("running", {}, {}, "end_unconfirmed"),
    ("resolved", {}, {}, "terminal_checkpoint"),
])
def test_report_uses_positive_checkpoint_evidence(tmp_path, status, messages, requests, phase):
    enter(tmp_path)
    write_cp(tmp_path, document(status=status, messages=messages, requests=requests))
    page = observe(tmp_path)
    assert page["executions"][0]["observed_state"] == phase
    expected = "terminal_closure_unconfirmed" if phase == "terminal_checkpoint" else phase
    assert page["page_drain_blockers"] == [{"execution_id": "wf-one", "reasons": [expected]}]


@pytest.mark.parametrize("fault", ["fork", "cycle", "missing-entry", "wrong-id", "wrong-affinity", "changed-graph"])
def test_corrupt_or_ambiguous_history_cannot_look_terminal(tmp_path, fault):
    enter(tmp_path)
    leaf = document(status="resolved")
    if fault == "fork":
        write_cp(tmp_path, document("fork", "entry", status="failed"))
    elif fault == "cycle":
        leaf["previous_checkpoint_id"] = "leaf"
    elif fault == "missing-entry":
        (tmp_path / "checkpoints" / "entry.json").unlink()
    elif fault == "wrong-id":
        leaf["checkpoint_id"] = "other"
    elif fault == "wrong-affinity":
        leaf["state"][AFFINITY_STATE_KEY] = replace(affinity(), installation_id="other").to_document()
    else:
        leaf["graph_signature_hash"] = "b" * 64
    write_cp(tmp_path, leaf, "leaf")
    row, = observe(tmp_path)["executions"]
    assert row["observed_state"] == "unresolved" and row["issues"]


@pytest.mark.parametrize("separate", [True, False])
def test_legacy_queue_is_observed_without_consumption_or_adoption(tmp_path, separate):
    queue, approvals, path = sources(tmp_path)
    invocation = prepare(queue, approvals)
    legacy_path = tmp_path / "legacy.db" if separate else path
    legacy = SqliteIncidentContinuationStore(legacy_path, payload_codec=CODEC)
    legacy.enqueue(invocation)
    previous, old_job = snapshot(path), legacy.get("apr-one")
    report = observe(tmp_path, legacy_database=legacy_path)
    row, = report["executions"]
    if separate:
        assert report["legacy_queue"] == "unattributed_separate_store"
        assert row["legacy_jobs"] == {} and "approval_in_both_queues" not in row["issues"]
    else:
        assert report["legacy_queue"] == "correlated"
        assert row["legacy_jobs"] == row["candidate_jobs"] == {"pending": 1}
        assert "approval_in_both_queues" in row["issues"]
    assert snapshot(path) == previous and legacy.get("apr-one") == old_job


def test_legacy_absence_and_admin_residuals_do_not_appear_as_zero_at_customer_level(tmp_path):
    queue, approvals, path = sources(tmp_path)
    prepare(queue, approvals)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DELETE FROM incident_executions")
        db.commit()
    write_cp(tmp_path, document())
    legacy_path = tmp_path / "old.db"
    legacy = SqliteIncidentContinuationStore(legacy_path, payload_codec=CODEC)
    legacy.enqueue(prepare(stores(tmp_path)[0], approvals, "two"))
    with closing(sqlite3.connect(path)) as db:
        db.execute("DELETE FROM incident_executions WHERE execution_id='wf-two'")
        db.commit()
    assert observe(tmp_path)["executions"] == []
    assert observe(tmp_path)["legacy_queue"] == "unavailable"
    fields = dict(database=path, checkpoints=tmp_path / "checkpoints")
    assert sqlite_store_residuals(**fields)["legacy_jobs_without_attributed_approval"] is None
    residuals = sqlite_store_residuals(**fields, legacy_database=legacy_path)
    assert residuals["approvals_without_admission"] == residuals["candidate_jobs_without_admission"] == 2
    assert residuals["legacy_jobs_without_attributed_approval"] == 1
    assert residuals["checkpoints"] == {"execution_without_admission": 1}
    assert "wf-one" not in json.dumps(residuals) and "installation_id" not in residuals


def test_terminal_checkpoint_and_pending_work_conflict(tmp_path):
    queue = enter(tmp_path)
    _, approvals, _ = stores(tmp_path)
    prepare(queue, approvals, name="two")
    hold = document("cp-two", "entry", execution="wf-two", requests={"req-two": None})
    write_cp(tmp_path, hold)
    write_cp(tmp_path, document("finished", "cp-two", execution="wf-two", status="resolved"))
    _, row = observe(tmp_path)["executions"]
    assert row["issues"] == ["terminal_with_unfinished_work"]


def test_export_is_durable_minimal_and_exclusive(tmp_path):
    enter(tmp_path)
    cp = document(messages={"next": [{"__pickled__": "THIS-IS-NOT-A-PICKLE"}]})
    cp["state"]["private"] = "secret-alert"
    write_cp(tmp_path, cp)
    config = tmp_path / "consumer.json"
    config.write_text(json.dumps(affinity().to_document()), encoding="utf-8")
    output = tmp_path / "inventory.json"
    args = ["--database", str(tmp_path / "state.db"), "--checkpoints", str(tmp_path / "checkpoints"),
            "--consumer-affinity", str(config), "--output", str(output)]
    main(args)
    saved = output.read_bytes()
    assert json.loads(saved)["executions"][0]["observed_state"] == "in_progress"
    assert all(value not in saved for value in (b"secret-alert", b"__pickled__", b"NOT-A-PICKLE"))
    with pytest.raises(FileExistsError):
        main(args)
    assert output.read_bytes() == saved
    with pytest.raises(TypeError):
        write_inventory_report(tmp_path / "bad.json", {"bad": object()})
    assert not (tmp_path / "bad.json").exists()
    args[-1] = str(tmp_path / "checkpoints" / "forbidden.json")
    with pytest.raises(SystemExit):
        main(args)
    assert not (tmp_path / "checkpoints" / "forbidden.json").exists()


def test_bad_fingerprint_aborts_export_and_keeps_sources(tmp_path):
    enter(tmp_path)
    with closing(sqlite3.connect(tmp_path / "state.db")) as conn:
        conn.execute("UPDATE incident_executions SET affinity_sha256=?", ("b"*64,))
        conn.commit()
    with pytest.raises(ValueError, match="fingerprint"):
        observe(tmp_path)


@pytest.mark.parametrize("matching", [True, False])
def test_separate_legacy_store_requires_independent_approval_correlation(tmp_path, matching):
    from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
    from src.runtime.procedure.approval_store import SqlitePendingApprovalStore

    queue, approvals, path = sources(tmp_path)
    invocation = prepare(queue, approvals)
    old_db = tmp_path / "legacy.db"
    old_approvals = SqlitePendingApprovalStore(old_db)
    old_approvals.register(PendingApprovalCorrelation(approval_id="apr-one", workflow_id="wf-one",
        checkpoint_id="cp-one" if matching else "different", request_id="req-one"))
    SqliteIncidentContinuationStore(old_db, payload_codec=CODEC).enqueue(invocation)
    report = observe(tmp_path, legacy_database=old_db)
    assert report["legacy_queue"] == "verified_correlations_only"
    assert report["executions"][0]["legacy_jobs"] == ({"pending": 1} if matching else {})
    admin = sqlite_store_residuals(database=path, checkpoints=tmp_path / "checkpoints", legacy_database=old_db)
    assert admin["legacy_jobs_without_attributed_approval"] == int(not matching)


def test_misbound_candidate_job_is_reported_without_disclosing_its_status(tmp_path):
    queue, approvals, path = sources(tmp_path)
    prepare(queue, approvals)
    foreign, _, _ = stores(tmp_path, replace(affinity(), installation_id="foreign"))
    foreign.admit(execution_id="foreign-case", input_sha256="f"*64)
    with closing(sqlite3.connect(path)) as db:
        db.execute("UPDATE incident_affine_continuation_jobs SET execution_id='foreign-case'")
        db.commit()
    previous = snapshot(path)
    ours, = observe(tmp_path)["executions"]
    theirs, = observe(tmp_path, foreign.execution_affinity)["executions"]
    assert "candidate_approval_owner_conflict" in ours["issues"]
    assert "candidate_approval_unconfirmed" in theirs["issues"]
    assert ours["candidate_jobs"] == theirs["candidate_jobs"] == {}
    assert "foreign" not in json.dumps(ours) and "wf-one" not in json.dumps(theirs)
    assert snapshot(path) == previous


def test_global_export_is_explicit_and_cannot_be_mixed_with_customer_options(tmp_path):
    sources(tmp_path)
    output = tmp_path / "global.json"
    args = ["--database", str(tmp_path / "state.db"), "--checkpoints", str(tmp_path / "checkpoints"),
            "--output", str(output), "--store-residuals"]
    for extra in (["--limit", "1"], ["--consumer-affinity", "fake.json"]):
        with pytest.raises(SystemExit):
            main(args + extra)
        assert not output.exists()
    main(args)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["coverage"] == "whole_store_operator_only" and "executions" not in result


@pytest.mark.asyncio
async def test_native_file_checkpoints_with_windows_text_encoding_survive_observation(tmp_path, monkeypatch):
    import locale
    from agent_framework._workflows import _checkpoint

    # Exercise the pinned SDK writer and restorer with Windows text-file semantics on every OS.
    def windows_open(path, mode="r", **kwargs):
        if "b" not in mode:
            kwargs.setdefault("encoding", "cp1252")
        return open(path, mode, **kwargs)

    monkeypatch.setattr(_checkpoint, "open", windows_open, raising=False)
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=False: "cp1252")
    state = setup(tmp_path)
    await pending(state)
    directory = tmp_path / "checkpoints"
    original = {path: path.read_bytes() for path in directory.glob("*.json")}
    assert any(b"\xe9" in content for content in original.values())
    before = snapshot(state.path)
    row, = observe(tmp_path, state.case.affinity)["executions"]
    assert row["observed_state"] == "hitl_checkpoint" and row["issues"] == []
    assert sqlite_store_residuals(database=state.path, checkpoints=directory)["approvals_without_admission"] == 0
    assert snapshot(state.path) == before
    assert {path: path.read_bytes() for path in original} == original
    active, _ = worker(state)
    assert (await active.process_next_once()).value == "completed"
    done, = observe(tmp_path, state.case.affinity)["executions"]
    assert done["observed_state"] == "terminal_checkpoint" and done["issues"] == []


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32", "utf-16-le", "utf-32-be"])
def test_existing_unicode_checkpoint_formats_preserve_text(tmp_path, monkeypatch, encoding):
    import locale
    from src.persistence.execution_inventory import _read_file

    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=False: "cp1252")
    doc = {"text": "acción, €, 東京"}
    path = tmp_path / "checkpoint.json"
    path.write_bytes(json.dumps(doc, ensure_ascii=False).encode(encoding))
    assert _read_file(path) == doc


@pytest.mark.parametrize("scope", ["installation", "store"])
def test_origin_encoding_can_be_declared_for_transferred_files(tmp_path, monkeypatch, scope):
    import locale
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=False: "utf-8")
    enter(tmp_path)
    directory = tmp_path / "checkpoints"
    leaf = document(status="resolved")
    leaf["metadata"] = {"note": "Проверка"}
    write_cp(tmp_path, leaf)
    for path in directory.glob("*.json"):
        doc = json.loads(path.read_bytes())
        doc["metadata"] = leaf["metadata"]
        path.write_bytes(json.dumps(doc, ensure_ascii=False).encode("cp1251"))
    out = tmp_path / "result.json"
    cmd = ["--database", str(tmp_path / "state.db"), "--checkpoints", str(directory), "--output", str(out)]
    if scope == "store":
        cmd += ["--store-residuals"]
    else:
        cfg = tmp_path / "affinity.json"
        cfg.write_text(json.dumps(affinity().to_document()), encoding="utf-8")
        cmd += ["--consumer-affinity", str(cfg)]
    with pytest.raises(UnicodeDecodeError):
        main(cmd)
    assert not out.exists()
    main(cmd + ["--checkpoint-encoding", "cp1251"])
    saved = json.loads(out.read_text(encoding="utf-8"))
    if scope == "store":
        assert saved["checkpoints"] == {"entry_without_execution_id": 1}
    else:
        assert saved["executions"][0]["observed_state"] == "terminal_checkpoint"


def test_explicit_source_encoding_wins_for_ambiguous_bytes(tmp_path):
    from src.persistence.execution_inventory import _read_file

    path = tmp_path / "checkpoint.json"
    path.write_bytes(b'{"label":"\xc3\xa9"}')
    assert _read_file(path, "cp1252") == {"label": "Ã©"}
    assert _read_file(path, "utf-8") == {"label": "é"}


@pytest.mark.parametrize("defect", ["invalid_byte", "duplicate", "malformed", "broken_bom"])
def test_legacy_checkpoint_errors_prevent_export_without_rewriting_source(tmp_path, monkeypatch, defect):
    import locale
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=False: "cp1252")
    sources(tmp_path)
    directory = tmp_path / "checkpoints"
    payloads = {"invalid_byte": b'{"note":"\x81"}', "duplicate": b'{"\xe9":1,"\xe9":2}',
                "malformed": b'{"note":"\xe9"', "broken_bom": b'\xef\xbb\xbf{"note":"\xe9"}'}
    original = payloads[defect]
    path = directory / "broken.json"
    path.write_bytes(original)
    output = tmp_path / "result.json"
    with pytest.raises(ValueError):
        main(["--store-residuals", "--database", str(tmp_path / "state.db"),
              "--checkpoints", str(directory), "--output", str(output)])
    assert not output.exists() and path.read_bytes() == original

def test_historical_database_without_receipt_table_remains_readable(tmp_path):
    enter(tmp_path)
    with closing(sqlite3.connect(tmp_path / "state.db")) as connection:
        connection.execute("DROP TABLE incident_rejection_closures")
    row, = observe(tmp_path)["executions"]
    assert row["rejection_receipt"] == {"status": "unavailable"}


def test_drain_page_filters_release_and_preserves_cursor(tmp_path):
    queue, _, _ = sources(tmp_path)
    scope = affinity()
    previous = replace(scope, release=replace(scope.release, release_id="previous"))
    old, _, _ = stores(tmp_path, previous)
    old.admit(execution_id="a-old", input_sha256="a"*64)
    queue.admit(execution_id="b-current", input_sha256="a"*64)
    first = observe(tmp_path, limit=1)
    assert first["page_drain_blockers"] == [] and first["next_after"] == "a-old"
    second = observe(tmp_path, after=first["next_after"])
    assert second["drain_release_id"] == scope.release.release_id
    assert second["page_drain_blockers"] == [
        {"execution_id": "b-current", "reasons": ["start_unconfirmed"]}]


def test_complete_drain_reads_last_page_and_keeps_other_customers_private(tmp_path):
    from src.persistence.execution_inventory import sqlite_release_drain

    queue, _, path = sources(tmp_path)
    scope = affinity()
    older, _, _ = stores(tmp_path, replace(scope, release=replace(scope.release, release_id="older")))
    older.admit(execution_id="first", input_sha256="a"*64)
    queue.admit(execution_id="last", input_sha256="b"*64)
    other, _, _ = stores(tmp_path, replace(scope, installation_id="other"))
    other.admit(execution_id="foreign-sensitive", input_sha256="b"*64)
    queue.begin_drain()
    report = sqlite_release_drain(database=path, checkpoints=tmp_path/"checkpoints", consumer=scope, page_size=1)
    assert report["pages_read"] == 2 and report["admission_closed"] and report["status"] == "blocked"
    assert report["execution_blockers"] == [{"execution_id": "last", "reasons": ["start_unconfirmed"]}]
    assert "foreign-sensitive" not in json.dumps(report)


def test_complete_drain_requires_closed_admissions_and_attributed_history(tmp_path):
    from src.persistence.execution_inventory import sqlite_release_drain

    queue, _, path = sources(tmp_path)
    args = dict(database=path, checkpoints=tmp_path/"checkpoints", consumer=affinity())
    assert sqlite_release_drain(**args)["status"] == "blocked"
    queue.begin_drain()
    assert sqlite_release_drain(**args)["coverage_gaps"] == ["legacy_queue_unavailable"]
    SqliteIncidentContinuationStore(path, payload_codec=CODEC)
    assert sqlite_release_drain(**args)["status"] == "no_observed_blockers"
    write_cp(tmp_path, document(execution="unassigned"))
    report = sqlite_release_drain(**args)
    assert report["status"] == "unconfirmed"
    assert report["coverage_gaps"] == ["unattributed_store_history"]
    assert "unassigned" not in json.dumps(report)
