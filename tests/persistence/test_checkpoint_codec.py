"""Historical wire compatibility and rejection before SQL or unpickling."""
import json
from pathlib import Path

import pytest
from agent_framework import WorkflowCheckpoint, WorkflowCheckpointException
from agent_framework._workflows._checkpoint_encoding import encode_checkpoint_value

from src.persistence import checkpoint_codec as codec_module
from src.persistence.checkpoint_codec import WorkflowCheckpointCodec
from src.persistence.azure_sql.checkpoint_storage import AzureSqlCheckpointStorage
from src.workflows.incident_resolution.checkpoint_storage import incident_checkpoint_allowed_types


class UnlistedState:
    pass


def checkpoint(**kwargs):
    return WorkflowCheckpoint(workflow_name="incident-resolution", graph_signature_hash="synthetic", **kwargs)


def test_write_remains_byte_compatible_with_published_serializer():
    item = checkpoint(state={"text": "histórico", "count": 1})
    original = json.dumps(encode_checkpoint_value(item.to_dict()), ensure_ascii=False,
                          sort_keys=True, separators=(",", ":"))
    codec = WorkflowCheckpointCodec()
    assert codec.encode(item) == original
    assert codec.decode(original).to_dict() == item.to_dict()


def test_reads_immutable_fixture_created_by_published_pre_extraction_code():
    payload = (Path(__file__).resolve().parents[1] /
               "fixtures/checkpoints/incident_v1_before_e3.json").read_text(encoding="utf-8")
    codec = WorkflowCheckpointCodec(allowed_types=frozenset(incident_checkpoint_allowed_types()))
    restored = codec.decode(payload)
    assert restored.version == "1.0"
    assert restored.workflow_name == "incident-resolution"
    assert len(restored.pending_request_info_events) == 1


@pytest.mark.parametrize("payload", [
    "null", "[]", "{}", '{"version":"2.0"}', '{"version":1}',
    '{"version":true}', '{"version":"1.0","version":"1.0"}',
    '{"version":"1.0","state":{"a":1,"a":2}}', "{",
], ids=["null", "array", "missing-version", "future-version", "numeric-version",
        "boolean-version", "duplicate-version", "duplicate-state-key", "invalid-json"])
def test_unsupported_or_ambiguous_format_rejected_before_sdk_decoder(payload, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid format reached object reconstruction")
    monkeypatch.setattr(codec_module, "decode_checkpoint_value", forbidden)
    with pytest.raises(WorkflowCheckpointException):
        WorkflowCheckpointCodec().decode(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unlisted-state", "future-version"])
async def test_unrestorable_state_never_opens_sql_connection(kind):
    def forbidden():
        raise AssertionError("Invalid checkpoint reached SQL")
    store = AzureSqlCheckpointStorage(connection_factory=forbidden)
    item = checkpoint(state={"custom": UnlistedState()}) if kind == "unlisted-state" else checkpoint(version="2.0")
    with pytest.raises(WorkflowCheckpointException):
        await store.save(item)


def test_allowed_application_type_roundtrips_and_missing_allowlist_rejects():
    key = f"{UnlistedState.__module__}:{UnlistedState.__qualname__}"
    codec = WorkflowCheckpointCodec(allowed_types=frozenset({key}))
    payload = codec.encode(checkpoint(state={"custom": UnlistedState()}))
    assert isinstance(codec.decode(payload).state["custom"], UnlistedState)
    with pytest.raises(WorkflowCheckpointException):
        WorkflowCheckpointCodec().decode(payload)
