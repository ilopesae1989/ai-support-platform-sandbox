from __future__ import annotations

from contextlib import (
    closing,
)

from dataclasses import (
    dataclass,
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
    El recheck_id ya fue consumido.

    Es una condición de seguridad monotónica,
    no un error transitorio.

    Nunca debe provocar retry automático del
    mismo WaitRecheckSignal.
    """

    pass


class WaitRecheckConsumptionLedger(
    Protocol
):
    """
    Autoridad monotónica externa al checkpoint.

    Garantiza:

        recheck_id
            ->
        claim exactamente una vez

    Restaurar un checkpoint histórico no puede
    devolver autoridad a un recheck_id consumido.
    """

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
                    recheck_id=trusted_id
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
    Autoridad durable mínima para sandbox/MVP.

    Propiedades:

    - persistencia entre instancias;
    - recheck_id único;
    - claim atómico;
    - replay fail-closed;
    - autoridad externa al checkpoint;
    - sin delete/reset/reopen.

    No es la implementación Azure SQL productiva.
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
        with closing(
            self._connect()
        ) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                wait_recheck_consumption_claims (
                    recheck_id TEXT PRIMARY KEY
                )
                """
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

        connection = (
            self._connect()
        )

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
