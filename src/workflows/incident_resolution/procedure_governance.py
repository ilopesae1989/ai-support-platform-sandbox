from __future__ import annotations

from dataclasses import dataclass


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
