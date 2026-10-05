from __future__ import annotations

import json

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .procedure_catalog import ProcedureCatalog


PROCEDURE_GOVERNANCE_SCHEMA_VERSION = "1.0"


class ProcedureGovernanceError(ValueError):
    pass


def _require_exact_nonblank_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ProcedureGovernanceError(
            field_name
            + " debe ser string."
        )

    if not value:
        raise ProcedureGovernanceError(
            field_name
            + " no puede estar vacío."
        )

    if not value.strip():
        raise ProcedureGovernanceError(
            field_name
            + " no puede estar vacío."
        )

    if value != value.strip():
        raise ProcedureGovernanceError(
            field_name
            + " debe ser exacto."
        )

    return value


@dataclass(frozen=True)
class ProcedureGovernanceMetadata:
    procedure_id: str
    procedure_version: str
    owner: str
    governance_approval_status: str
    governance_approval_reference: str | None
    compatible_previous_versions: tuple[str, ...]
    rollback_version: str | None

    def __post_init__(
        self,
    ) -> None:
        _require_exact_nonblank_string(
            self.procedure_id,
            "procedure_id",
        )

        _require_exact_nonblank_string(
            self.procedure_version,
            "procedure_version",
        )

        _require_exact_nonblank_string(
            self.owner,
            "owner",
        )

        if (
            self.governance_approval_status
            not in {
                "pending",
                "approved",
                "rejected",
            }
        ):
            raise ProcedureGovernanceError(
                "governance_approval_status "
                "debe ser pending, approved "
                "o rejected."
            )

        if (
            self.governance_approval_status
            == "pending"
        ):
            if (
                self.governance_approval_reference
                is not None
            ):
                raise ProcedureGovernanceError(
                    "pending no puede tener "
                    "governance_approval_reference."
                )

        else:
            _require_exact_nonblank_string(
                self.governance_approval_reference,
                "governance_approval_reference",
            )

        if (
            type(
                self.compatible_previous_versions
            )
            is not tuple
        ):
            raise ProcedureGovernanceError(
                "compatible_previous_versions "
                "debe ser tuple."
            )

        seen: set[str] = set()

        for version in (
            self.compatible_previous_versions
        ):
            exact_version = (
                _require_exact_nonblank_string(
                    version,
                    "compatible_previous_versions",
                )
            )

            if (
                exact_version
                == self.procedure_version
            ):
                raise ProcedureGovernanceError(
                    "compatible_previous_versions "
                    "no puede incluir "
                    "procedure_version."
                )

            if exact_version in seen:
                raise ProcedureGovernanceError(
                    "compatible_previous_versions "
                    "contiene duplicados."
                )

            seen.add(
                exact_version
            )

        if self.rollback_version is None:
            return

        exact_rollback = (
            _require_exact_nonblank_string(
                self.rollback_version,
                "rollback_version",
            )
        )

        if (
            exact_rollback
            == self.procedure_version
        ):
            raise ProcedureGovernanceError(
                "rollback_version no puede "
                "ser procedure_version."
            )

        if (
            exact_rollback
            not in self.compatible_previous_versions
        ):
            raise ProcedureGovernanceError(
                "rollback_version debe estar "
                "declarada en "
                "compatible_previous_versions."
            )

class ProcedureGovernanceRegistry:
    """
    Binding determinista entre governance metadata
    y una identidad exacta existente en
    ProcedureCatalog.

    Este registry no concede capability,
    no concede HITL y no ejecuta operaciones.
    """

    def __init__(
        self,
        *,
        catalog: ProcedureCatalog,
        metadata: Iterable[
            ProcedureGovernanceMetadata
        ],
    ) -> None:
        if not isinstance(
            catalog,
            ProcedureCatalog,
        ):
            raise ProcedureGovernanceError(
                "catalog debe ser ProcedureCatalog."
            )

        resolved: dict[
            tuple[str, str],
            ProcedureGovernanceMetadata,
        ] = {}

        for item in metadata:
            if not isinstance(
                item,
                ProcedureGovernanceMetadata,
            ):
                raise ProcedureGovernanceError(
                    "metadata debe contener "
                    "ProcedureGovernanceMetadata."
                )

            key = (
                item.procedure_id,
                item.procedure_version,
            )

            if key in resolved:
                raise ProcedureGovernanceError(
                    "Governance metadata duplicada "
                    "para la identidad exacta."
                )

            if not catalog.contains(
                item.procedure_id,
                item.procedure_version,
            ):
                raise ProcedureGovernanceError(
                    "La identidad gobernada no existe "
                    "en ProcedureCatalog."
                )

            for previous_version in (
                item.compatible_previous_versions
            ):
                if not catalog.contains(
                    item.procedure_id,
                    previous_version,
                ):
                    raise ProcedureGovernanceError(
                        "compatible_previous_versions "
                        "debe referenciar versiones "
                        "existentes del mismo "
                        "procedure_id."
                    )

            resolved[key] = item

        self._metadata = MappingProxyType(
            resolved
        )

    def count(
        self,
    ) -> int:
        return len(
            self._metadata
        )

    def contains(
        self,
        procedure_id: str,
        procedure_version: str,
    ) -> bool:
        return (
            procedure_id,
            procedure_version,
        ) in self._metadata

    def get(
        self,
        procedure_id: str,
        procedure_version: str,
    ) -> ProcedureGovernanceMetadata:
        item = self._metadata.get(
            (
                procedure_id,
                procedure_version,
            )
        )

        if item is None:
            raise ProcedureGovernanceError(
                "No existe governance metadata "
                "para la identidad exacta."
            )

        return item

class ProcedureGovernanceApprovalPolicy:
    """
    Gate determinista de governance approval.

    Sólo comprueba la metadata exacta ya
    registrada para procedure_id +
    procedure_version.

    No resuelve owner.
    No concede HITL.
    No concede capability.
    No ejecuta rollback.
    No hace fallback de versión.
    """

    def __init__(
        self,
        *,
        registry: ProcedureGovernanceRegistry,
    ) -> None:
        if not isinstance(
            registry,
            ProcedureGovernanceRegistry,
        ):
            raise ProcedureGovernanceError(
                "registry debe ser "
                "ProcedureGovernanceRegistry."
            )

        self._registry = registry

    def require_governance_approval(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
    ) -> ProcedureGovernanceMetadata:
        metadata = self._registry.get(
            procedure_id,
            procedure_version,
        )

        if (
            metadata.governance_approval_status
            != "approved"
        ):
            raise ProcedureGovernanceError(
                "El procedimiento exacto no tiene "
                "governance approval approved."
            )

        return metadata

def _unique_governance_json_object(
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


def _read_governance_manifest(
    path: Path,
) -> object:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            ),
            object_pairs_hook=(
                _unique_governance_json_object
            ),
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        raise ProcedureGovernanceError(
            "No pudo cargarse el manifiesto "
            "de procedure governance."
        ) from None


def load_procedure_governance(
    path,
    *,
    catalog: ProcedureCatalog,
) -> ProcedureGovernanceRegistry:
    """
    Carga metadata declarativa de governance
    y la vincula a un ProcedureCatalog explícito.

    No concede capability, HITL ni autoridad
    operacional.
    """

    payload = _read_governance_manifest(
        Path(path)
    )

    if (
        not isinstance(
            payload,
            dict,
        )
        or set(payload)
        != {
            "schema_version",
            "procedures",
        }
    ):
        raise ProcedureGovernanceError(
            "Manifiesto de governance raíz inválido."
        )

    if (
        payload["schema_version"]
        != PROCEDURE_GOVERNANCE_SCHEMA_VERSION
    ):
        raise ProcedureGovernanceError(
            "schema_version de governance "
            "no soportada."
        )

    procedures = payload[
        "procedures"
    ]

    if type(procedures) is not list:
        raise ProcedureGovernanceError(
            "procedures debe ser array JSON."
        )

    expected_record_keys = {
        "procedure_id",
        "procedure_version",
        "owner",
        "governance_approval_status",
        "governance_approval_reference",
        "compatible_previous_versions",
        "rollback_version",
    }

    metadata: list[
        ProcedureGovernanceMetadata
    ] = []

    for raw_item in procedures:
        if (
            not isinstance(
                raw_item,
                dict,
            )
            or set(raw_item)
            != expected_record_keys
        ):
            raise ProcedureGovernanceError(
                "Definición de governance inválida."
            )

        compatible_versions = raw_item[
            "compatible_previous_versions"
        ]

        if type(compatible_versions) is not list:
            raise ProcedureGovernanceError(
                "compatible_previous_versions "
                "debe ser array JSON."
            )

        item = ProcedureGovernanceMetadata(
            procedure_id=raw_item[
                "procedure_id"
            ],
            procedure_version=raw_item[
                "procedure_version"
            ],
            owner=raw_item[
                "owner"
            ],
            governance_approval_status=raw_item[
                "governance_approval_status"
            ],
            governance_approval_reference=raw_item[
                "governance_approval_reference"
            ],
            compatible_previous_versions=tuple(
                compatible_versions
            ),
            rollback_version=raw_item[
                "rollback_version"
            ],
        )

        metadata.append(
            item
        )

    return ProcedureGovernanceRegistry(
        catalog=catalog,
        metadata=tuple(
            metadata
        ),
    )
