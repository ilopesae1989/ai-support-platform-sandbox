from __future__ import annotations

import json

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


PROCEDURE_CATALOG_SCHEMA_VERSION = "1.0"

DEFAULT_PROCEDURE_CATALOG_PATH = (
    Path(__file__).with_name(
        "procedure_catalog.v1.json"
    )
)


class ProcedureCatalogError(ValueError):
    pass


class ProcedureNotFoundError(ProcedureCatalogError):
    pass


class DuplicateProcedureDefinitionError(ProcedureCatalogError):
    pass


class ProcedureNotPublishedError(ProcedureCatalogError):
    pass


class ProcedureIdentityMismatchError(ProcedureCatalogError):
    pass


@dataclass(frozen=True)
class ProcedureDefinition:
    procedure_id: str
    procedure_version: str
    procedure_name: str
    lifecycle: str
    step_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("procedure_id", self.procedure_id),
            ("procedure_version", self.procedure_version),
            ("procedure_name", self.procedure_name),
        ):
            if not isinstance(value, str):
                raise ProcedureCatalogError(
                    f"{name} debe ser string."
                )

            if not value or not value.strip():
                raise ProcedureCatalogError(
                    f"{name} no puede estar vacío."
                )

            if value != value.strip():
                raise ProcedureCatalogError(
                    f"{name} no puede requerir normalización."
                )

        if self.lifecycle not in {
            "draft",
            "published",
            "retired",
        }:
            raise ProcedureCatalogError(
                "lifecycle debe ser draft, published o retired."
            )

        if not isinstance(self.step_ids, tuple):
            raise ProcedureCatalogError(
                "step_ids debe ser tuple."
            )

        if not self.step_ids:
            raise ProcedureCatalogError(
                "step_ids no puede estar vacío."
            )

        seen: set[str] = set()

        for step_id in self.step_ids:
            if not isinstance(step_id, str):
                raise ProcedureCatalogError(
                    "step_ids sólo admite strings."
                )

            if not step_id or not step_id.strip():
                raise ProcedureCatalogError(
                    "step_ids no admite valores vacíos."
                )

            if step_id != step_id.strip():
                raise ProcedureCatalogError(
                    "step_ids no admite normalización."
                )

            if step_id in seen:
                raise ProcedureCatalogError(
                    "step_ids contiene valores duplicados."
                )

            seen.add(step_id)


class ProcedureCatalog:
    """
    Catálogo determinista de procedimientos versionados.

    La identidad es exacta:
        procedure_id + procedure_version

    No resuelve capabilities, no ejecuta agentes y no
    contiene autoridad cloud.
    """

    def __init__(
        self,
        *,
        definitions: Iterable[ProcedureDefinition],
    ) -> None:
        resolved: dict[
            tuple[str, str],
            ProcedureDefinition,
        ] = {}

        for definition in definitions:
            if not isinstance(
                definition,
                ProcedureDefinition,
            ):
                raise ProcedureCatalogError(
                    "Sólo pueden catalogarse ProcedureDefinition."
                )

            key = (
                definition.procedure_id,
                definition.procedure_version,
            )

            if key in resolved:
                raise DuplicateProcedureDefinitionError(
                    "Ya existe una definición para "
                    f"procedure_id={definition.procedure_id!r}, "
                    f"procedure_version={definition.procedure_version!r}."
                )

            resolved[key] = definition

        self._definitions = MappingProxyType(
            resolved
        )

    def count(self) -> int:
        return len(self._definitions)

    def contains(
        self,
        procedure_id: str,
        procedure_version: str,
    ) -> bool:
        return (
            procedure_id,
            procedure_version,
        ) in self._definitions

    def get(
        self,
        procedure_id: str,
        procedure_version: str,
    ) -> ProcedureDefinition:
        key = (
            procedure_id,
            procedure_version,
        )

        definition = self._definitions.get(
            key
        )

        if definition is None:
            raise ProcedureNotFoundError(
                "No existe procedimiento exacto para "
                f"procedure_id={procedure_id!r}, "
                f"procedure_version={procedure_version!r}."
            )

        return definition

    def resolve_published(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        procedure_name: str,
    ) -> ProcedureDefinition:
        definition = self.get(
            procedure_id,
            procedure_version,
        )

        if (
            procedure_name
            != definition.procedure_name
        ):
            raise ProcedureIdentityMismatchError(
                "procedure_name no coincide con la "
                "identidad canónica catalogada."
            )

        if definition.lifecycle != "published":
            raise ProcedureNotPublishedError(
                "El procedimiento exacto no está publicado."
            )

        return definition

    def contains_step(
        self,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> bool:
        definition = self._definitions.get(
            (
                procedure_id,
                procedure_version,
            )
        )

        if definition is None:
            return False

        return step_id in definition.step_ids


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


def _load_json_payload(
    path: Path,
) -> object:
    try:
        text = path.read_text(
            encoding="utf-8"
        )

        return json.loads(
            text,
            object_pairs_hook=_unique_json_object,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        raise ProcedureCatalogError(
            "No pudo cargarse el manifiesto "
            "de Procedure Catalog."
        ) from None


def load_procedure_catalog(
    path,
) -> ProcedureCatalog:
    manifest_path = Path(path)

    payload = _load_json_payload(
        manifest_path
    )

    if not isinstance(payload, dict):
        raise ProcedureCatalogError(
            "El manifiesto debe ser un objeto JSON."
        )

    if set(payload) != {
        "schema_version",
        "procedures",
    }:
        raise ProcedureCatalogError(
            "El manifiesto contiene miembros raíz inválidos."
        )

    if (
        payload["schema_version"]
        != PROCEDURE_CATALOG_SCHEMA_VERSION
    ):
        raise ProcedureCatalogError(
            "schema_version no soportada."
        )

    procedures = payload["procedures"]

    if type(procedures) is not list:
        raise ProcedureCatalogError(
            "procedures debe ser un array JSON."
        )

    expected_fields = {
        "procedure_id",
        "procedure_version",
        "procedure_name",
        "lifecycle",
        "step_ids",
    }

    definitions: list[
        ProcedureDefinition
    ] = []

    for item in procedures:
        if (
            not isinstance(item, dict)
            or set(item) != expected_fields
        ):
            raise ProcedureCatalogError(
                "El manifiesto contiene una "
                "definición de procedimiento inválida."
            )

        step_ids = item["step_ids"]

        if type(step_ids) is not list:
            raise ProcedureCatalogError(
                "step_ids debe ser un array JSON."
            )

        try:
            definition = ProcedureDefinition(
                procedure_id=item["procedure_id"],
                procedure_version=(
                    item["procedure_version"]
                ),
                procedure_name=item["procedure_name"],
                lifecycle=item["lifecycle"],
                step_ids=tuple(step_ids),
            )
        except ProcedureCatalogError:
            raise
        except Exception:
            raise ProcedureCatalogError(
                "El manifiesto contiene una "
                "definición no válida."
            ) from None

        definitions.append(
            definition
        )

    return ProcedureCatalog(
        definitions=definitions
    )


def build_default_procedure_catalog() -> ProcedureCatalog:
    return load_procedure_catalog(
        DEFAULT_PROCEDURE_CATALOG_PATH
    )
