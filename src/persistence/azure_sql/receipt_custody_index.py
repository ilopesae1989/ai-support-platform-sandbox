"""DB-API index for complete custody records; explicit transactions, no DDL.

Requires the separately qualified dbo.f27_receipt_custody_v1 schema. An INSERT
error is never classified by exception text as a duplicate. A lost COMMIT
response remains unknown until a separate read-only reconciliation.
"""
from __future__ import annotations
import hashlib
import re

from src.persistence.receipt_custody import IndexOutcome
from src.workflows.incident_resolution.mcp_receipt_trust import parse_subject_json_v1

_INSERT = """INSERT INTO dbo.f27_receipt_custody_v1
(logical_sha256, record_sha256, record_bytes)
VALUES (%(logical)s, %(digest)s, %(record)s)"""
_SELECT = """SELECT record_sha256, record_bytes FROM dbo.f27_receipt_custody_v1
WHERE logical_sha256 = %(logical)s"""


def _parameters(logical, raw):
    if type(logical) is not str or not re.fullmatch("[0-9a-f]{64}", logical):
        raise ValueError("Invalid logical digest")
    if type(raw) is not bytes or not 0 < len(raw) <= 65536:
        raise ValueError("Invalid custody record size")
    parse_subject_json_v1(raw)
    return {"logical": bytes.fromhex(logical), "digest": hashlib.sha256(raw).digest(), "record": raw}


def _close(cursor, connection):
    for obj in (cursor, connection):
        if obj is not None:
            try:
                obj.close()
            except Exception:
                pass


class AzureSqlReceiptCustodyIndex:
    def __init__(self, *, connection_factory, read_connection_factory):
        if not callable(connection_factory) or not callable(read_connection_factory):
            raise TypeError("Explicit writer and reader SQL factories required")
        self._factory, self._read_factory = connection_factory, read_connection_factory

    def insert_once(self, logical_sha256: str, record: bytes) -> IndexOutcome:
        params = _parameters(logical_sha256, record)
        conn = cursor = None
        try:
            conn = self._factory()
            if getattr(conn, "autocommit", None) is not False:
                return IndexOutcome.UNKNOWN
            cursor = conn.cursor()
            try:
                cursor.execute(_INSERT, params)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return IndexOutcome.UNKNOWN
            try:
                conn.commit()
            except Exception:
                # Do not retry, infer rollback, or turn a failed commit into success.
                return IndexOutcome.UNKNOWN
            return IndexOutcome.COMMITTED
        except Exception:
            return IndexOutcome.UNKNOWN
        finally:
            _close(cursor, conn)

    def read(self, logical_sha256: str, record: bytes) -> IndexOutcome:
        params = _parameters(logical_sha256, record)
        conn = cursor = None
        try:
            conn = self._read_factory()
            cursor = conn.cursor()
            cursor.execute(_SELECT, {"logical": params["logical"]})
            first = cursor.fetchone()
            if first is None:
                return IndexOutcome.ABSENT
            if cursor.fetchone() is not None:
                return IndexOutcome.CONFLICT
            return (IndexOutcome.PRESENT if tuple(first) == (params["digest"], params["record"])
                    else IndexOutcome.CONFLICT)
        except Exception:
            return IndexOutcome.UNKNOWN
        finally:
            _close(cursor, conn)
