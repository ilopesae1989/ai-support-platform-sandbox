import pytest

from src.persistence.azure_sql.wait_recheck_consumption_ledger import (
    AzureSqlWaitRecheckConsumptionLedger,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    WaitRecheckAlreadyConsumedError,
    WaitRecheckBeginResult,
    WaitRecheckStatus,
)


class FakeIntegrityError(
    Exception
):
    pass


class FakeDatabase:
    def __init__(
        self,
    ):
        self.rows = {}


class FakeConnection:
    IntegrityError = FakeIntegrityError

    def __init__(
        self,
        database,
    ):
        self._database = database
        self._local = dict(
            database.rows
        )

        self.closed = False
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(
        self,
    ):
        return FakeCursor(
            self
        )

    def commit(
        self,
    ):
        self._database.rows = dict(
            self._local
        )

        self.commit_count += 1

    def rollback(
        self,
    ):
        self._local = dict(
            self._database.rows
        )

        self.rollback_count += 1

    def close(
        self,
    ):
        self.closed = True


class FakeCursor:
    def __init__(
        self,
        connection,
    ):
        self._connection = connection
        self._row = None
        self.closed = False

    def execute(
        self,
        sql,
        parameters,
    ):
        normalized = " ".join(
            str(sql)
            .lower()
            .split()
        )

        recheck_id = parameters.get(
            "recheck_id"
        )

        if (
            normalized.startswith(
                "select top (1) status"
            )
        ):
            status = (
                self._connection
                ._local
                .get(
                    recheck_id
                )
            )

            if status is None:
                self._row = None
            else:
                self._row = (
                    status,
                )

            return

        if (
            normalized.startswith(
                "insert into "
                "dbo.wait_recheck_consumption_claims"
            )
        ):
            if (
                recheck_id
                in self._connection._local
            ):
                raise FakeIntegrityError(
                    "duplicate"
                )

            status = parameters.get(
                "status",
                "completed",
            )

            self._connection._local[
                recheck_id
            ] = status

            return

        if normalized.startswith(
            "update dbo.wait_recheck_consumption_claims"
        ):
            current = (
                self._connection
                ._local
                .get(
                    recheck_id
                )
            )

            if (
                current
                == parameters[
                    "in_progress_status"
                ]
            ):
                self._connection._local[
                    recheck_id
                ] = parameters[
                    "completed_status"
                ]

            return

        if (
            normalized.startswith(
                "select top (1) 1"
            )
        ):
            if (
                recheck_id
                in self._connection._local
            ):
                self._row = (
                    1,
                )
            else:
                self._row = None

            return

        raise AssertionError(
            "SQL inesperado: "
            + normalized
        )

    def fetchone(
        self,
    ):
        return self._row

    def close(
        self,
    ):
        self.closed = True


def _ledger():
    database = FakeDatabase()
    connections = []

    def factory():
        connection = FakeConnection(
            database
        )

        connections.append(
            connection
        )

        return connection

    return (
        database,
        connections,
        AzureSqlWaitRecheckConsumptionLedger(
            connection_factory=factory
        ),
    )


def test_azure_sql_begin_claims_then_resumes_same_in_progress_recheck():
    (
        database,
        connections,
        ledger,
    ) = _ledger()

    recheck_id = (
        "rchk-azure-state-001"
    )

    first = ledger.begin(
        recheck_id
    )

    assert (
        first
        == WaitRecheckBeginResult.CLAIMED
    )

    assert (
        database.rows[
            recheck_id
        ]
        == "in_progress"
    )

    second = ledger.begin(
        recheck_id
    )

    assert (
        second
        == WaitRecheckBeginResult.RESUMED
    )

    assert (
        ledger.status(
            recheck_id
        )
        == WaitRecheckStatus.IN_PROGRESS
    )

    assert all(
        connection.closed
        for connection
        in connections
    )


def test_azure_sql_complete_is_idempotent_and_blocks_future_begin():
    (
        database,
        _,
        ledger,
    ) = _ledger()

    recheck_id = (
        "rchk-azure-state-002"
    )

    ledger.begin(
        recheck_id
    )

    ledger.complete(
        recheck_id
    )

    assert (
        database.rows[
            recheck_id
        ]
        == "completed"
    )

    assert (
        ledger.status(
            recheck_id
        )
        == WaitRecheckStatus.COMPLETED
    )

    ledger.complete(
        recheck_id
    )

    with pytest.raises(
        WaitRecheckAlreadyConsumedError
    ):
        ledger.begin(
            recheck_id
        )


def test_azure_sql_complete_requires_existing_begin_and_rolls_back():
    (
        database,
        connections,
        ledger,
    ) = _ledger()

    with pytest.raises(
        RuntimeError
    ):
        ledger.complete(
            "rchk-azure-state-missing"
        )

    assert database.rows == {}

    assert any(
        connection.rollback_count >= 1
        for connection
        in connections
    )

    assert all(
        connection.closed
        for connection
        in connections
    )