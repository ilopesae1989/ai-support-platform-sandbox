"""Insert-only attempt ownership and private recovery journal for the attestor.

Uses a separately deployed table with a unique binary claim key. A failed or
ambiguous commit never grants ownership, even if a later read finds a row.
No automatic retry, UPDATE, DELETE, MERGE, DDL or duplicate-error guessing.
"""
from __future__ import annotations

import hashlib
import re

from src.workflows.incident_resolution.mcp_receipt_trust import canonical_subject_v1

_INSERT = """INSERT INTO dbo.f27_attestation_journal_v1
(claim_sha256, owner_sha256, record_sha256, record_bytes)
VALUES (%(claim)s, %(owner)s, %(digest)s, %(record)s)"""
_SELECT = """SELECT owner_sha256, record_sha256, record_bytes
FROM dbo.f27_attestation_journal_v1 WHERE claim_sha256 = %(claim)s"""
_MAX_BYTES = 1048576


def _key(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("Exact SHA256 key required")
    return bytes.fromhex(value)


def _stage(owner, stage):
    _key(owner)
    if stage not in {"NATIVE_APPROVAL", "NATIVE_EXECUTION", "NATIVE_INPUT", "PAIR_0", "PAIR_1", "PAIR_2", "COMPLETE"}:
        raise ValueError("Unknown journal stage")
    return hashlib.sha256(canonical_subject_v1({"domain": "f27-journal-stage-v1",
                                              "owner": owner, "stage": stage})).hexdigest()


def _close(*objects):
    for obj in objects:
        if obj is not None:
            try:
                obj.close()
            except Exception:
                pass


class AzureSqlAttestationJournal:
    def __init__(self, *, connection_factory, read_connection_factory):
        if not callable(connection_factory) or not callable(read_connection_factory):
            raise TypeError("Explicit SQL factories required")
        self._write, self._read = connection_factory, read_connection_factory

    def _read_row(self, key):
        claim = _key(key)
        conn = cur = None
        try:
            conn = self._read()
            cur = conn.cursor()
            cur.execute(_SELECT, {"claim": claim})
            row = cur.fetchone()
            if row is None:
                return None
            if cur.fetchone() is not None:
                raise ValueError("Journal uniqueness violated")
            owner, digest, raw = row
            raw = bytes(raw)
            if (len(owner) != 32 or not 0 < len(raw) <= _MAX_BYTES
                    or hashlib.sha256(raw).digest() != digest):
                raise ValueError("Invalid journal readback")
            return bytes(owner), bytes(digest), raw
        finally:
            _close(cur, conn)

    def reserve(self, keys, owner, record):
        keys = tuple(keys)
        if not keys or len(keys) > 8 or len(set(keys)) != len(keys):
            raise ValueError("Bounded distinct claims required")
        claims, owner_bytes = tuple(_key(k) for k in keys), _key(owner)
        if type(record) is not bytes or not 0 < len(record) <= _MAX_BYTES:
            raise ValueError("Bounded private journal bytes required")
        digest = hashlib.sha256(record).digest()
        conn = cur = None
        try:
            conn = self._write()
            if getattr(conn, "autocommit", None) is not False:
                return False
            cur = conn.cursor()
            try:
                for claim in claims:
                    cur.execute(_INSERT, {"claim": claim, "owner": owner_bytes,
                                          "digest": digest, "record": record})
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False
            try:
                conn.commit()
            except Exception:
                return False
        except Exception:
            return False
        finally:
            _close(cur, conn)
        # Separate read connections; a successful read cannot repair an unknown
        # commit because the unknown branch already returned False above.
        try:
            return all(self._read_row(key) == (owner_bytes, digest, record) for key in keys)
        except Exception:
            return False

    def put(self, owner, stage, record):
        return self.reserve((_stage(owner, stage),), owner, record)

    def get(self, owner, stage):
        row = self._read_row(_stage(owner, stage))
        if row is None:
            return None
        if row[0] != _key(owner):
            raise ValueError("Journal owner mismatch")
        return row[2]

    def read_claim(self, owner):
        row = self._read_row(owner)
        if row is None:
            return None
        if row[0] != _key(owner):
            raise ValueError("Claim owner mismatch")
        return row[2]
