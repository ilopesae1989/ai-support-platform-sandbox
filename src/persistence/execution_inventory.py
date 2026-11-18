"""Observe one bounded page of admissions in a database read transaction."""
from codecs import BOM_UTF8
from collections import Counter
from contextlib import ExitStack, closing, contextmanager
import hashlib
import json
import locale
from pathlib import Path
import sqlite3

from src.runtime.execution_affinity import ExecutionAffinity, require_digest, require_identifier
from src.runtime.execution_inventory import ExecutionEvidence
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key in inventory source.')
        result[key] = value
    return result


def load_inventory_json(raw):
    return json.loads(raw, object_pairs_hook=_unique)


class _Reader:
    def __init__(self, connection, sql_server):
        self.connection = connection
        self.sql_server = sql_server
        self.prefix = 'dbo.' if sql_server else ''
        self.legacy_coverage = 'correlated'

    def bind(self, name):
        return f'%({name})s' if self.sql_server else f':{name}'

    def rows(self, statement, params=()):
        with closing(self.connection.cursor()) as cursor:
            if params:
                cursor.execute(statement, params)
            else:
                cursor.execute(statement)
            while batch := cursor.fetchmany(64):
                yield from batch

    def page(self, consumer, limit, after):
        if type(consumer) is not ExecutionAffinity:
            raise TypeError('A trusted consumer affinity is required.')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Page size must be between 1 and 100.')
        if after is not None:
            require_identifier(after, 'after')
        field = ('JSON_VALUE(affinity_json, \'$.installation_id\') COLLATE Latin1_General_100_BIN2'
                 if self.sql_server else "json_extract(affinity_json, '$.installation_id') COLLATE BINARY")
        top = f'TOP ({limit + 1})' if self.sql_server else ''
        tail = '' if self.sql_server else f'LIMIT {limit + 1}'
        query = f'''SELECT {top} execution_id, input_sha256, affinity_sha256, affinity_json
                    FROM {self.prefix}incident_executions WHERE {field} = {self.bind("installation")}
                    AND execution_id > {self.bind("after")} ORDER BY execution_id {tail}'''
        records = list(self.rows(query, {'installation': consumer.installation_id, 'after': after or ''}))
        evidence = {}
        for execution_id, input_hash, affinity_hash, document in records:
            affinity = ExecutionAffinity.from_document(load_inventory_json(document))
            if affinity.installation_id != consumer.installation_id or affinity.fingerprint != affinity_hash:
                raise ValueError('Admission scope or fingerprint mismatch.')
            require_digest(input_hash, 'input_sha256')
            require_identifier(execution_id, 'execution_id')
            evidence[execution_id] = ExecutionEvidence(execution_id, affinity)
        more = len(records) > limit
        if more:
            evidence.pop(records[-1][0])
        return evidence, records[limit - 1][0] if more else None

    def terminal_receipts(self, evidence, kind):
        table = {"rejection": "incident_rejection_closures", "resolution": "incident_resolution_closures"}[kind]
        if not evidence:
            return
        exists = (f"SELECT OBJECT_ID(N'dbo.{table}', N'U')" if self.sql_server
                  else f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not any(row[0] for row in self.rows(exists)):
            return
        for item in evidence.values():
            receipt = {'status': 'absent'}
            query = (f'SELECT c.approval_id, j.execution_id, j.status FROM {self.prefix}{table} c '
                     f'LEFT JOIN {self.prefix}incident_affine_continuation_jobs j ON j.approval_id = c.approval_id '
                     f'WHERE c.execution_id = {self.bind("execution")}')
            for approval, owner, status in self.rows(query, {'execution': item.execution_id}):
                if owner != item.execution_id or status != 'completed':
                    item.issues.add(f'{kind}_receipt_conflict')
                    receipt = {'status': 'conflict'}
                else:
                    receipt = {
                        'status': 'recorded', 'approval_sha256': hashlib.sha256(approval.encode('utf-8')).hexdigest(),
                        'notification_delivery': 'unconfirmed',
                    }
            setattr(item, kind + '_receipt', receipt)

    def approvals(self, execution):
        approvals = {}
        for approval, workflow, request, cp, status in self.rows(
            f'SELECT approval_id, workflow_id, request_id, checkpoint_id, consumption_status '
            f'FROM {self.prefix}pending_approvals WHERE workflow_id = {self.bind("execution")}', {'execution': execution.execution_id}
        ):
            if workflow != execution.execution_id or status not in ('pending', 'claimed', 'completed'):
                raise ValueError('Invalid approval identity or status.')
            if request in execution.approvals or approval in approvals:
                raise ValueError('Duplicate approval correlation.')
            approvals[approval] = (request, cp, status)
            execution.approvals[request] = (cp, status)
        return approvals

    def jobs(self, execution, approvals, legacy):
        candidate_ids = set()
        rows = self.rows(f'SELECT approval_id, execution_id, status FROM {self.prefix}incident_affine_continuation_jobs '
                         f'WHERE execution_id = {self.bind("execution")} OR approval_id IN '
                         f'(SELECT approval_id FROM {self.prefix}pending_approvals WHERE workflow_id = {self.bind("execution")})',
                         {'execution': execution.execution_id})
        for approval, owner, status in rows:
            if owner != execution.execution_id:
                execution.issues.add('candidate_approval_owner_conflict')
                continue
            if approval not in approvals:
                execution.issues.add('candidate_approval_unconfirmed')
                continue
            _job(execution, 'candidate', status, approvals[approval][2])
            candidate_ids.add(approval)
        if legacy and legacy.legacy_coverage != 'unattributed_separate_store':
            for approval, (request, cp, consumed) in approvals.items():
                if legacy is not self:
                    linked = list(legacy.rows('SELECT workflow_id, request_id, checkpoint_id '
                                              'FROM pending_approvals WHERE approval_id = :id', {'id': approval}))
                    if linked != [(execution.execution_id, request, cp)]:
                        continue
                for actual, status in legacy.rows(f'SELECT approval_id, status FROM {legacy.prefix}incident_continuation_jobs '
                                                 f'WHERE approval_id = {legacy.bind("approval")}', {'approval': approval}):
                    if actual != approval:
                        raise ValueError('Legacy approval correlation mismatch.')
                    _job(execution, 'legacy', status, consumed)
                    if approval in candidate_ids:
                        execution.issues.add('approval_in_both_queues')


def _job(execution, queue, status, approval_status):
    if status not in ('pending', 'claimed', 'failed', 'completed'):
        raise ValueError('Invalid continuation status.')
    if status == 'completed' and approval_status != 'completed':
        execution.issues.add('completion_conflict')
    execution.jobs.append((queue, status))


def _observe(doc, stored_id, evidence):
    if doc['workflow_name'] != 'incident-resolution':
        return
    execution = evidence.get(doc['state'].get(EXECUTION_ID_STATE_KEY))
    if execution:
        execution.observe_checkpoint(doc, stored_id)


def _report(consumer, evidence, following, legacy):
    return {'schema': 'incident-inventory-page-v1', 'installation_id': consumer.installation_id,
            'consumer_affinity_sha256': consumer.fingerprint, 'next_after': following,
            'coverage': 'attributed_admissions', 'unattributed_history': 'separate_store_review',
            'legacy_queue': legacy.legacy_coverage if legacy else 'unavailable',
            'executions': [item.describe(consumer) for item in evidence.values()]}


def _sqlite(path):
    return sqlite3.connect(Path(path).resolve(strict=True).as_uri() + '?mode=ro', uri=True)


@contextmanager
def _sqlite_sources(database, checkpoints, legacy_database):
    """Use a stable checkpoint copy for reproducible observations across file/DB boundaries."""
    directory = Path(checkpoints).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('Existing checkpoint directory required.')
    with ExitStack() as stack:
        def reader(path):
            conn = stack.enter_context(closing(_sqlite(path)))
            with closing(conn.cursor()) as cursor:
                cursor.execute('BEGIN')
            return _Reader(conn, False)
        current = reader(database)
        legacy = current
        if legacy_database is not None and Path(legacy_database).resolve() != Path(database).resolve():
            legacy = reader(legacy_database)
            has_approvals = list(legacy.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_approvals'"))
            legacy.legacy_coverage = 'verified_correlations_only' if has_approvals else 'unattributed_separate_store'
        if not list(legacy.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='incident_continuation_jobs'")):
            if legacy_database is not None:
                raise ValueError('Specified legacy database lacks its queue.')
            legacy = None
        yield current, legacy, directory


def _read_file(path, checkpoint_encoding=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular checkpoint file.')
    raw = path.read_bytes()
    if checkpoint_encoding is not None:
        return load_inventory_json(raw.decode(checkpoint_encoding))

    try:
        return load_inventory_json(raw)
    except UnicodeDecodeError as error:
        # FileCheckpointStorage writes text with the interpreter's default encoding.
        # Only unmarked input interpreted as UTF-8 can be a legacy native text file.
        if error.encoding != 'utf-8' or raw.startswith(BOM_UTF8):
            raise
        native_encoding = locale.getpreferredencoding(False)
        return load_inventory_json(raw.decode(native_encoding))


def sqlite_inventory_page(*, database, checkpoints, consumer, limit=50, after=None,
                          legacy_database=None, checkpoint_encoding=None):
    with _sqlite_sources(database, checkpoints, legacy_database) as (current, legacy, directory):
        evidence, following = current.page(consumer, limit, after)
        current.terminal_receipts(evidence, "rejection")
        current.terminal_receipts(evidence, "resolution")
        for item in evidence.values():
            current.jobs(item, current.approvals(item), legacy)

        def lookup(parent):
            # parent passed require_identifier, including its length and alphabet checks.
            path = directory / f'{parent}.json'
            return _read_file(path, checkpoint_encoding) if path.exists() else None

        if evidence:
            for path in directory.iterdir():
                if path.suffix == '.json':
                    _observe(_read_file(path, checkpoint_encoding), path.stem, evidence)
            for item in evidence.values():
                item.verify_entry(lookup)
        return _report(consumer, evidence, following, legacy)


@contextmanager
def _sql_source(connection_factory):
    """Dedicated read connection. Snapshot isolation must already be available."""
    with closing(connection_factory()) as conn:
        if getattr(conn, 'autocommit', None) is not False:
            raise ValueError('Inventory requires autocommit=False.')
        try:
            with closing(conn.cursor()) as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL SNAPSHOT')
            yield _Reader(conn, True)
        finally:
            conn.rollback()


def azure_sql_inventory_page(*, connection_factory, consumer, limit=50, after=None):
    with _sql_source(connection_factory) as reader:
        evidence, following = reader.page(consumer, limit, after)
        reader.terminal_receipts(evidence, "rejection")
        reader.terminal_receipts(evidence, "resolution")
        for item in evidence.values():
            reader.jobs(item, reader.approvals(item), reader)
            rows = reader.rows("""SELECT checkpoint_id, payload_json FROM dbo.workflow_checkpoints
                WHERE workflow_name = 'incident-resolution'
                AND JSON_VALUE(payload_json, '$.state.incident_execution_id')
                COLLATE Latin1_General_100_BIN2 = %(execution)s""", {'execution': item.execution_id})
            for stored_id, raw in rows:
                doc = load_inventory_json(raw)
                if doc['workflow_name'] != 'incident-resolution':
                    raise ValueError('Checkpoint workflow mismatch.')
                item.observe_checkpoint(doc, stored_id)

            def lookup(parent):
                roots = list(reader.rows("""SELECT payload_json FROM dbo.workflow_checkpoints
                    WHERE workflow_name = 'incident-resolution' AND checkpoint_id = %(parent)s""",
                    {'parent': parent}))
                return load_inventory_json(roots[0][0]) if roots else None
            item.verify_entry(lookup)
        return _report(consumer, evidence, following, reader)


def _residuals(reader, legacy, documents):
    """Store-wide operator view. Return counts only, never attach them to an installation."""
    def count(query):
        row, = reader.rows(query)
        return row[0]

    tables = reader.prefix
    total = 'COUNT_BIG(*)' if reader.sql_server else 'COUNT(*)'
    # Approval/legacy columns can inherit a different database collation.
    binary = ' COLLATE Latin1_General_100_BIN2' if reader.sql_server else ''

    def missing_admission(table, field):
        return count(f'SELECT {total} FROM {tables}{table} record WHERE NOT EXISTS '
                     f'(SELECT 1 FROM {tables}incident_executions e WHERE e.execution_id = record.{field}{binary})')

    checkpoints = Counter()
    for doc in documents:
        if doc['workflow_name'] != 'incident-resolution':
            continue
        if doc['version'] != '1.0' or not isinstance(doc['state'], dict):
            raise ValueError('Unexpected checkpoint format in store review.')
        key = doc['state'].get(EXECUTION_ID_STATE_KEY)
        if key is None:
            if doc['previous_checkpoint_id'] is None:
                checkpoints['entry_without_execution_id'] += 1
            else:
                checkpoints['other_without_execution_id'] += 1
        else:
            require_identifier(key, 'execution_id')
            if not list(reader.rows(f'SELECT execution_id FROM {tables}incident_executions '
                                    f'WHERE execution_id = {reader.bind("id")}', {'id': key})):
                checkpoints['execution_without_admission'] += 1

    orphan_jobs = None
    if legacy is reader:
        orphan_jobs = count(f'SELECT {total} FROM {tables}incident_continuation_jobs j WHERE NOT EXISTS '
                            f'(SELECT 1 FROM {tables}pending_approvals a JOIN {tables}incident_executions e '
                            f'ON e.execution_id = a.workflow_id{binary} WHERE a.approval_id = j.approval_id)')
    elif legacy is not None:
        orphan_jobs = 0
        if legacy.legacy_coverage == 'unattributed_separate_store':
            (orphan_jobs,), = legacy.rows('SELECT COUNT(*) FROM incident_continuation_jobs')
        else:
            for approval, workflow, request, cp in legacy.rows(
                'SELECT j.approval_id, a.workflow_id, a.request_id, a.checkpoint_id '
                'FROM incident_continuation_jobs j LEFT JOIN pending_approvals a ON a.approval_id = j.approval_id'
            ):
                match = list(reader.rows('SELECT a.workflow_id, a.request_id, a.checkpoint_id '
                                         'FROM pending_approvals a JOIN incident_executions e '
                                         'ON e.execution_id = a.workflow_id WHERE a.approval_id = :id', {'id': approval}))
                orphan_jobs += int(match != [(workflow, request, cp)])
    return {
        'schema': 'incident-store-residuals-v1', 'coverage': 'whole_store_operator_only',
        'checkpoints': dict(sorted(checkpoints.items())),
        'approvals_without_admission': missing_admission('pending_approvals', 'workflow_id'),
        'candidate_jobs_without_admission': missing_admission('incident_affine_continuation_jobs', 'execution_id'),
        'legacy_jobs_without_attributed_approval': orphan_jobs,
    }


def sqlite_store_residuals(*, database, checkpoints, legacy_database=None, checkpoint_encoding=None):
    with _sqlite_sources(database, checkpoints, legacy_database) as (reader, legacy, directory):
        documents = (_read_file(path, checkpoint_encoding) for path in directory.iterdir() if path.suffix == '.json')
        return _residuals(reader, legacy, documents)


def azure_sql_store_residuals(*, connection_factory):
    with _sql_source(connection_factory) as reader:
        # Keyset batches leave no active result set for the admission lookups;
        # this also works on a connection without multiple active result sets.
        def documents():
            after = ''
            while True:
                rows = list(reader.rows("""SELECT TOP (64) checkpoint_id, payload_json FROM dbo.workflow_checkpoints
                    WHERE workflow_name = 'incident-resolution' AND checkpoint_id > %(after)s
                    ORDER BY checkpoint_id""", {'after': after}))
                if not rows:
                    return
                for _, raw in rows:
                    yield load_inventory_json(raw)
                after = rows[-1][0]
        return _residuals(reader, reader, documents())
