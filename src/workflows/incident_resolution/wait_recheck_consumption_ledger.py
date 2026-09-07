from __future__ import annotations

from contextlib import (
    closing,
)

from dataclasses import (
    dataclass,
)

from enum import (
    Enum,
)

from pathlib import (
    Path,
)

from threading import (
    Lock,
)

from typing import (
    Protocol,
)

import sqlite3


class WaitRecheckAlreadyConsumedError(
    RuntimeError
):
    """
    El recheck_id ya está COMPLETED.

    Es una condición de seguridad monotónica,
    no un error transitorio.

    Un recheck IN_PROGRESS puede reanudarse.
    Un recheck COMPLETED nunca recupera autoridad.
    """

    pass


class WaitRecheckStatus(
    str,
    Enum,
):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class WaitRecheckBeginResult(
    str,
    Enum,
):
    CLAIMED = "claimed"
    RESUMED = "resumed"


class WaitRecheckConsumptionLedger(
    Protocol
):
    """
    Autoridad monotónica externa al checkpoint.

    Estado durable:

        ABSENT
            ->
        IN_PROGRESS
            ->
        COMPLETED

    IN_PROGRESS permite reanudar el response
    superstep después de un crash.

    COMPLETED bloquea cualquier replay histórico.
    """

    def begin(
        self,
        recheck_id: str,
    ) -> WaitRecheckBeginResult:
        ...

    def complete(
        self,
        recheck_id: str,
    ) -> None:
        ...

    def status(
        self,
        recheck_id: str,
    ) -> WaitRecheckStatus | None:
        ...

    def claim(
        self,
        recheck_id: str,
    ) -> None:
        ...

    def contains(
        self,
        recheck_id: str,
    ) -> bool:
        ...


@dataclass(
    frozen=True
)
class WaitRecheckConsumptionRecord:
    recheck_id: str
    status: WaitRecheckStatus


def _validate_recheck_id(
    recheck_id: str,
) -> str:
    if (
        not isinstance(
            recheck_id,
            str,
        )
        or not recheck_id
        or not recheck_id.strip()
        or recheck_id
        != recheck_id.strip()
    ):
        raise ValueError(
            "recheck_id debe ser un string "
            "exacto no vacío."
        )

    return recheck_id


class InMemoryWaitRecheckConsumptionLedger:
    """
    Autoridad monotónica para tests y sandbox
    de proceso único.

    No forma parte del checkpoint del workflow.
    """

    def __init__(
        self,
    ) -> None:
        self._records: dict[
            str,
            WaitRecheckConsumptionRecord,
        ] = {}

        self._lock = Lock()

    def begin(
        self,
        recheck_id: str,
    ) -> WaitRecheckBeginResult:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with self._lock:
            record = self._records.get(
                trusted_id
            )

            if record is None:
                self._records[
                    trusted_id
                ] = (
                    WaitRecheckConsumptionRecord(
                        recheck_id=trusted_id,
                        status=(
                            WaitRecheckStatus
                            .IN_PROGRESS
                        ),
                    )
                )

                return (
                    WaitRecheckBeginResult
                    .CLAIMED
                )

            if (
                record.status
                == WaitRecheckStatus.IN_PROGRESS
            ):
                return (
                    WaitRecheckBeginResult
                    .RESUMED
                )

            raise (
                WaitRecheckAlreadyConsumedError(
                    "WAIT recheck ya completado. "
                    "recheck_id="
                    f"{trusted_id!r}."
                )
            )

    def complete(
        self,
        recheck_id: str,
    ) -> None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with self._lock:
            record = self._records.get(
                trusted_id
            )

            if record is None:
                raise RuntimeError(
                    "WAIT recheck no fue iniciado. "
                    "recheck_id="
                    f"{trusted_id!r}."
                )

            if (
                record.status
                == WaitRecheckStatus.COMPLETED
            ):
                return

            self._records[
                trusted_id
            ] = (
                WaitRecheckConsumptionRecord(
                    recheck_id=trusted_id,
                    status=(
                        WaitRecheckStatus
                        .COMPLETED
                    ),
                )
            )

    def status(
        self,
        recheck_id: str,
    ) -> WaitRecheckStatus | None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with self._lock:
            record = self._records.get(
                trusted_id
            )

            if record is None:
                return None

            return record.status

    def claim(
        self,
        recheck_id: str,
    ) -> None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with self._lock:
            if trusted_id in self._records:
                raise (
                    WaitRecheckAlreadyConsumedError(
                        "WAIT recheck ya consumido. "
                        "recheck_id="
                        f"{trusted_id!r}."
                    )
                )

            self._records[
                trusted_id
            ] = (
                WaitRecheckConsumptionRecord(
                    recheck_id=trusted_id,
                    status=(
                        WaitRecheckStatus
                        .COMPLETED
                    ),
                )
            )

    def contains(
        self,
        recheck_id: str,
    ) -> bool:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with self._lock:
            return (
                trusted_id
                in self._records
            )

    def count(
        self,
    ) -> int:
        with self._lock:
            return len(
                self._records
            )


class SqliteWaitRecheckConsumptionLedger:
    """
    Autoridad durable sandbox/MVP.

    Legacy claim() conserva semántica binaria
    y crea directamente COMPLETED.

    El flujo WAIT crash-safe utiliza:

        begin()
        complete()
        status()
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        if not isinstance(
            database_path,
            (
                str,
                Path,
            ),
        ):
            raise TypeError(
                "database_path debe ser str o Path."
            )

        if isinstance(
            database_path,
            str,
        ):
            if (
                not database_path
                or not database_path.strip()
                or database_path
                != database_path.strip()
            ):
                raise ValueError(
                    "database_path debe ser un "
                    "path exacto no vacío."
                )

        self._database_path = Path(
            database_path
        )

        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        return sqlite3.connect(
            self._database_path,
            timeout=30,
        )

    def _initialize(
        self,
    ) -> None:
        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                wait_recheck_consumption_claims (
                    recheck_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                        DEFAULT 'completed'
                        CHECK (
                            status IN (
                                'in_progress',
                                'completed'
                            )
                        )
                )
                """
            )

            columns = {
                str(
                    row[1]
                )
                for row
                in connection.execute(
                    """
                    PRAGMA table_info(
                        wait_recheck_consumption_claims
                    )
                    """
                ).fetchall()
            }

            if "status" not in columns:
                connection.execute(
                    """
                    ALTER TABLE
                    wait_recheck_consumption_claims
                    ADD COLUMN status TEXT NOT NULL
                        DEFAULT 'completed'
                        CHECK (
                            status IN (
                                'in_progress',
                                'completed'
                            )
                        )
                    """
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    @staticmethod
    def _decode_status(
        value,
    ) -> WaitRecheckStatus:
        try:
            return WaitRecheckStatus(
                str(
                    value
                )
            )

        except ValueError as exc:
            raise RuntimeError(
                "WAIT recheck contiene status "
                "durable inválido."
            ) from exc

    def begin(
        self,
        recheck_id: str,
    ) -> WaitRecheckBeginResult:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT status
                FROM wait_recheck_consumption_claims
                WHERE recheck_id = ?
                LIMIT 1
                """,
                (
                    trusted_id,
                ),
            ).fetchone()

            if row is None:
                connection.execute(
                    """
                    INSERT INTO
                    wait_recheck_consumption_claims (
                        recheck_id,
                        status
                    )
                    VALUES (?, ?)
                    """,
                    (
                        trusted_id,
                        (
                            WaitRecheckStatus
                            .IN_PROGRESS
                            .value
                        ),
                    ),
                )

                connection.commit()

                return (
                    WaitRecheckBeginResult
                    .CLAIMED
                )

            durable_status = (
                self._decode_status(
                    row[0]
                )
            )

            if (
                durable_status
                == WaitRecheckStatus.IN_PROGRESS
            ):
                connection.commit()

                return (
                    WaitRecheckBeginResult
                    .RESUMED
                )

            connection.rollback()

            raise (
                WaitRecheckAlreadyConsumedError(
                    "WAIT recheck ya completado. "
                    "recheck_id="
                    f"{trusted_id!r}."
                )
            )

        except WaitRecheckAlreadyConsumedError:
            connection.rollback()
            raise

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def complete(
        self,
        recheck_id: str,
    ) -> None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT status
                FROM wait_recheck_consumption_claims
                WHERE recheck_id = ?
                LIMIT 1
                """,
                (
                    trusted_id,
                ),
            ).fetchone()

            if row is None:
                connection.rollback()

                raise RuntimeError(
                    "WAIT recheck no fue iniciado. "
                    "recheck_id="
                    f"{trusted_id!r}."
                )

            durable_status = (
                self._decode_status(
                    row[0]
                )
            )

            if (
                durable_status
                == WaitRecheckStatus.COMPLETED
            ):
                connection.commit()
                return

            connection.execute(
                """
                UPDATE
                    wait_recheck_consumption_claims
                SET
                    status = ?
                WHERE
                    recheck_id = ?
                    AND status = ?
                """,
                (
                    WaitRecheckStatus
                    .COMPLETED
                    .value,
                    trusted_id,
                    WaitRecheckStatus
                    .IN_PROGRESS
                    .value,
                ),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def status(
        self,
        recheck_id: str,
    ) -> WaitRecheckStatus | None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM wait_recheck_consumption_claims
                WHERE recheck_id = ?
                LIMIT 1
                """,
                (
                    trusted_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._decode_status(
            row[0]
        )

    def claim(
        self,
        recheck_id: str,
    ) -> None:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            connection.execute(
                """
                INSERT INTO
                wait_recheck_consumption_claims (
                    recheck_id
                )
                VALUES (?)
                """,
                (
                    trusted_id,
                ),
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                WaitRecheckAlreadyConsumedError(
                    "WAIT recheck ya consumido. "
                    "recheck_id="
                    f"{trusted_id!r}."
                )
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def contains(
        self,
        recheck_id: str,
    ) -> bool:
        trusted_id = (
            _validate_recheck_id(
                recheck_id
            )
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM wait_recheck_consumption_claims
                WHERE recheck_id = ?
                LIMIT 1
                """,
                (
                    trusted_id,
                ),
            ).fetchone()

        return row is not None

    def count(
        self,
    ) -> int:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM wait_recheck_consumption_claims
                """
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "No pudo obtenerse el número "
                "de rechecks consumidos."
            )

        return int(
            row[0]
        )
