from __future__ import annotations

import json

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterable

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureCatalogError,
    build_default_procedure_catalog,
)


PROCEDURE_COMPATIBILITY_SCHEMA_VERSION = "1.0"
DEFAULT_PROCEDURE_COMPATIBILITY_PATH = Path(__file__).with_name(
    "procedure_compatibility.v1.json"
)


class ProcedureAdmissionError(ValueError):
    pass


class ProcedureNotAdmittedError(ProcedureAdmissionError):
    pass


def _require_exact_string(
    value: object,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise ProcedureAdmissionError(
            f"{field} debe ser string."
        )
    if not value or not value.strip():
        raise ProcedureAdmissionError(
            f"{field} no puede estar vacio."
        )
    if value != value.strip():
        raise ProcedureAdmissionError(
            f"{field} debe ser exacto."
        )
    return value


@dataclass(frozen=True)
class LegacyProcedureCompatibility:
    procedure_id: str
    procedure_version: str
    accepted_names: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_exact_string(
            self.procedure_id,
            "procedure_id",
        )
        _require_exact_string(
            self.procedure_version,
            "procedure_version",
        )

        if type(self.accepted_names) is not tuple:
            raise ProcedureAdmissionError(
                "accepted_names debe ser tuple."
            )
        if not self.accepted_names:
            raise ProcedureAdmissionError(
                "accepted_names no puede estar vacio."
            )

        seen: set[str] = set()
        for name in self.accepted_names:
            exact = _require_exact_string(
                name,
                "accepted_names",
            )
            if exact in seen:
                raise ProcedureAdmissionError(
                    "accepted_names contiene duplicados."
                )
            seen.add(exact)


@dataclass(frozen=True)
class ProcedureAdmission:
    procedure_id: str
    procedure_version: str
    procedure_name: str
    source: str

    def __post_init__(self) -> None:
        _require_exact_string(
            self.procedure_id,
            "procedure_id",
        )
        _require_exact_string(
            self.procedure_version,
            "procedure_version",
        )
        _require_exact_string(
            self.procedure_name,
            "procedure_name",
        )

        if self.source not in {
            "catalog",
            "legacy_compatibility",
        }:
            raise ProcedureAdmissionError(
                "source no soportado."
            )


class ProcedureAdmissionPolicy:
    def __init__(
        self,
        *,
        catalog: ProcedureCatalog,
        legacy_compatibility: Iterable[
            LegacyProcedureCompatibility
        ],
    ) -> None:
        if not isinstance(catalog, ProcedureCatalog):
            raise ProcedureAdmissionError(
                "catalog debe ser ProcedureCatalog."
            )

        legacy: dict[
            tuple[str, str],
            LegacyProcedureCompatibility,
        ] = {}

        for item in legacy_compatibility:
            if not isinstance(
                item,
                LegacyProcedureCompatibility,
            ):
                raise ProcedureAdmissionError(
                    "legacy_compatibility invalido."
                )

            key = (
                item.procedure_id,
                item.procedure_version,
            )

            if key in legacy:
                raise ProcedureAdmissionError(
                    "legacy_compatibility duplicado."
                )

            if catalog.contains(*key):
                raise ProcedureAdmissionError(
                    "legacy_compatibility solapa catalogo."
                )

            legacy[key] = item

        self.catalog = catalog
        self._legacy = MappingProxyType(legacy)

    def admit(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        procedure_name: str,
    ) -> ProcedureAdmission:
        if self.catalog.contains(
            procedure_id,
            procedure_version,
        ):
            try:
                definition = self.catalog.resolve_published(
                    procedure_id=procedure_id,
                    procedure_version=procedure_version,
                    procedure_name=procedure_name,
                )
            except ProcedureCatalogError:
                raise ProcedureNotAdmittedError(
                    "Procedimiento no admitido."
                ) from None

            return ProcedureAdmission(
                procedure_id=definition.procedure_id,
                procedure_version=definition.procedure_version,
                procedure_name=definition.procedure_name,
                source="catalog",
            )

        try:
            compatibility = self._legacy[
                (procedure_id, procedure_version)
            ]
        except (KeyError, TypeError):
            raise ProcedureNotAdmittedError(
                "Procedimiento no admitido."
            ) from None

        if (
            procedure_name
            not in compatibility.accepted_names
        ):
            raise ProcedureNotAdmittedError(
                "Procedimiento no admitido."
            )

        return ProcedureAdmission(
            procedure_id=procedure_id,
            procedure_version=procedure_version,
            procedure_name=procedure_name,
            source="legacy_compatibility",
        )


def _unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(
                "JSON contiene miembros duplicados."
            )
        result[key] = value
    return result


def _read_manifest(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        raise ProcedureAdmissionError(
            "No pudo cargarse el manifiesto."
        ) from None


def load_procedure_compatibility(
    path,
) -> tuple[LegacyProcedureCompatibility, ...]:
    payload = _read_manifest(Path(path))

    if (
        not isinstance(payload, dict)
        or set(payload)
        != {"schema_version", "procedures"}
    ):
        raise ProcedureAdmissionError(
            "Manifiesto raiz invalido."
        )

    if (
        payload["schema_version"]
        != PROCEDURE_COMPATIBILITY_SCHEMA_VERSION
    ):
        raise ProcedureAdmissionError(
            "schema_version no soportada."
        )

    procedures = payload["procedures"]
    if type(procedures) is not list:
        raise ProcedureAdmissionError(
            "procedures debe ser array JSON."
        )

    expected = {
        "procedure_id",
        "procedure_version",
        "accepted_names",
    }
    items: list[
        LegacyProcedureCompatibility
    ] = []
    seen: set[tuple[str, str]] = set()

    for raw in procedures:
        if (
            not isinstance(raw, dict)
            or set(raw) != expected
        ):
            raise ProcedureAdmissionError(
                "Definicion de compatibilidad invalida."
            )

        names = raw["accepted_names"]
        if type(names) is not list:
            raise ProcedureAdmissionError(
                "accepted_names debe ser array JSON."
            )

        item = LegacyProcedureCompatibility(
            procedure_id=raw["procedure_id"],
            procedure_version=raw[
                "procedure_version"
            ],
            accepted_names=tuple(names),
        )
        key = (
            item.procedure_id,
            item.procedure_version,
        )
        if key in seen:
            raise ProcedureAdmissionError(
                "Identidad legacy duplicada."
            )
        seen.add(key)
        items.append(item)

    return tuple(items)


def build_default_procedure_admission_policy(
) -> ProcedureAdmissionPolicy:
    return ProcedureAdmissionPolicy(
        catalog=build_default_procedure_catalog(),
        legacy_compatibility=load_procedure_compatibility(
            DEFAULT_PROCEDURE_COMPATIBILITY_PATH
        ),
    )
