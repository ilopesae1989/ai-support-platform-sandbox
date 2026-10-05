from __future__ import annotations

import json

from collections.abc import (
    Iterable,
)
from pathlib import Path

from .capability_registry import (
    CapabilityRegistry,
    build_default_capability_registry,
)

from .operational_capability import (
    OperationalCapability,
)

from .procedure_capability_binding import (
    ProcedureApplicability,
    ProcedureCapabilityBinding,
    ProcedureCapabilityBindingError,
)

from .procedure_catalog import (
    ProcedureCatalog,
    build_default_procedure_catalog,
)


PROCEDURE_CAPABILITY_BINDINGS_SCHEMA_VERSION = "1.0"

DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH = (
    Path(__file__).with_name(
        "procedure_capability_bindings.v1.json"
    )
)


class ProcedureCapabilityRegistryError(
    ValueError
):
    pass


class ProcedureCapabilityBindingNotFoundError(
    ProcedureCapabilityRegistryError
):
    pass


class DuplicateProcedureCapabilityBindingError(
    ProcedureCapabilityRegistryError
):
    pass


class ProcedureCapabilityRegistry:
    """
    Registro determinista:

        procedure_id
        procedure_version
        step_id
            ↓
        capability_id

    No existe:

    - fuzzy matching;
    - aliases;
    - wildcard de versión;
    - fallback a otro step;
    - selección mediante LLM.
    """

    def __init__(
        self,
        *,
        capability_registry: CapabilityRegistry,

        bindings: Iterable[
            ProcedureCapabilityBinding
        ],
    ) -> None:

        self._capability_registry = (
            capability_registry
        )

        self._bindings: dict[
            tuple[
                str,
                str,
                str,
            ],
            ProcedureCapabilityBinding,
        ] = {}

        for binding in bindings:
            self.register(
                binding
            )

    def register(
        self,
        binding: ProcedureCapabilityBinding,
    ) -> None:

        if not isinstance(
            binding,
            ProcedureCapabilityBinding,
        ):
            raise (
                ProcedureCapabilityRegistryError(
                    "Sólo pueden registrarse "
                    "ProcedureCapabilityBinding."
                )
            )

        #
        # Una capability inexistente nunca puede
        # adquirir autoridad mediante un binding.
        #
        self._capability_registry.get(
            binding.capability_id
        )

        key = (
            binding.procedure_id,
            binding.procedure_version,
            binding.step_id,
        )

        if key in self._bindings:
            raise (
                DuplicateProcedureCapabilityBindingError(
                    "Ya existe un binding para "
                    "procedure_id="
                    f"{binding.procedure_id!r}, "
                    "procedure_version="
                    f"{binding.procedure_version!r}, "
                    "step_id="
                    f"{binding.step_id!r}."
                )
            )

        self._bindings[
            key
        ] = binding

    def get_binding(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> ProcedureCapabilityBinding:

        key = (
            procedure_id,
            procedure_version,
            step_id,
        )

        binding = (
            self._bindings.get(
                key
            )
        )

        if binding is None:
            raise (
                ProcedureCapabilityBindingNotFoundError(
                    "No existe capability binding "
                    "para procedure_id="
                    f"{procedure_id!r}, "
                    "procedure_version="
                    f"{procedure_version!r}, "
                    "step_id="
                    f"{step_id!r}."
                )
            )

        return binding

    def resolve_capability(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> OperationalCapability:

        binding = self.get_binding(
            procedure_id=procedure_id,
            procedure_version=(
                procedure_version
            ),
            step_id=step_id,
        )

        return (
            self._capability_registry
            .get(
                binding.capability_id
            )
        )

    def resolve_applicable_capability(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
        operational_context: object,
    ) -> OperationalCapability:
        """
        Resuelve la capability sólo cuando el binding
        exacto también resulta aplicable al contexto
        operacional autoritativo.
        """

        from .operational_context import (
            OperationalContext,
        )

        if not isinstance(
            operational_context,
            OperationalContext,
        ):
            raise ProcedureCapabilityBindingError(
                "operational_context debe ser "
                "OperationalContext."
            )

        binding = self.get_binding(
            procedure_id=procedure_id,
            procedure_version=procedure_version,
            step_id=step_id,
        )

        applicability = binding.applicability

        if (
            operational_context.environment
            not in applicability.allowed_environments
        ):
            raise ProcedureCapabilityBindingError(
                "environment autoritativo no está "
                "permitido por el capability binding."
            )

        if (
            operational_context.incident_origin
            not in applicability.allowed_incident_origins
        ):
            raise ProcedureCapabilityBindingError(
                "incident_origin autoritativo no está "
                "permitido por el capability binding."
            )

        return self._capability_registry.get(
            binding.capability_id
        )


    def contains_binding(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> bool:
        """
        Comprueba exclusivamente la existencia del
        binding exacto.

        No aplica:

        - aliases;
        - fuzzy matching;
        - fallback de versión;
        - fallback de step.
        """

        return (
            (
                procedure_id,
                procedure_version,
                step_id,
            )
            in self._bindings
        )

    def count(
        self,
    ) -> int:
        return len(
            self._bindings
        )



def _unique_binding_json_object(
    pairs: list[
        tuple[
            str,
            object,
        ]
    ],
) -> dict[
    str,
    object,
]:
    result: dict[
        str,
        object,
    ] = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(
                "JSON contiene miembros duplicados."
            )

        result[key] = value

    return result


def _read_binding_manifest(
    path: Path,
) -> object:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            ),
            object_pairs_hook=(
                _unique_binding_json_object
            ),
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        raise ProcedureCapabilityRegistryError(
            "No pudo cargarse el manifiesto "
            "de procedure capability bindings."
        ) from None


def load_procedure_capability_bindings(
    path,
    *,
    catalog: ProcedureCatalog,
    capability_registry: CapabilityRegistry,
) -> ProcedureCapabilityRegistry:
    """
    Carga configuración declarativa de bindings
    exactos entre procedimientos versionados y
    capabilities ya instaladas.

    Autoridades separadas:

    - ProcedureCatalog valida procedure/version/step;
    - CapabilityRegistry valida capability_id;
    - ProcedureCapabilityBinding valida estructura
      exacta y applicability.

    No evalúa lifecycle publicado.
    No concede governance approval.
    No concede HITL.
    No hace fallback, aliases ni fuzzy matching.
    """

    if not isinstance(
        catalog,
        ProcedureCatalog,
    ):
        raise ProcedureCapabilityRegistryError(
            "catalog debe ser ProcedureCatalog."
        )

    if not isinstance(
        capability_registry,
        CapabilityRegistry,
    ):
        raise ProcedureCapabilityRegistryError(
            "capability_registry debe ser "
            "CapabilityRegistry."
        )

    try:
        manifest_path = Path(
            path
        )
    except (
        TypeError,
        ValueError,
    ):
        raise ProcedureCapabilityRegistryError(
            "path de manifiesto inválido."
        ) from None

    payload = _read_binding_manifest(
        manifest_path
    )

    if (
        not isinstance(
            payload,
            dict,
        )
        or set(
            payload
        )
        != {
            "schema_version",
            "bindings",
        }
    ):
        raise ProcedureCapabilityRegistryError(
            "Manifiesto raíz inválido."
        )

    if (
        payload[
            "schema_version"
        ]
        != PROCEDURE_CAPABILITY_BINDINGS_SCHEMA_VERSION
    ):
        raise ProcedureCapabilityRegistryError(
            "schema_version no soportada."
        )

    raw_bindings = payload[
        "bindings"
    ]

    if type(
        raw_bindings
    ) is not list:
        raise ProcedureCapabilityRegistryError(
            "bindings debe ser array JSON."
        )

    expected_binding_members = {
        "procedure_id",
        "procedure_version",
        "step_id",
        "capability_id",
        "applicability",
    }

    expected_applicability_members = {
        "allowed_environments",
        "allowed_incident_origins",
    }

    bindings: list[
        ProcedureCapabilityBinding
    ] = []

    for raw_binding in raw_bindings:
        if (
            not isinstance(
                raw_binding,
                dict,
            )
            or set(
                raw_binding
            )
            != expected_binding_members
        ):
            raise ProcedureCapabilityRegistryError(
                "Binding de procedimiento inválido."
            )

        raw_applicability = raw_binding[
            "applicability"
        ]

        if (
            not isinstance(
                raw_applicability,
                dict,
            )
            or set(
                raw_applicability
            )
            != expected_applicability_members
        ):
            raise ProcedureCapabilityRegistryError(
                "applicability inválida."
            )

        allowed_environments = (
            raw_applicability[
                "allowed_environments"
            ]
        )

        allowed_incident_origins = (
            raw_applicability[
                "allowed_incident_origins"
            ]
        )

        if type(
            allowed_environments
        ) is not list:
            raise ProcedureCapabilityRegistryError(
                "allowed_environments "
                "debe ser array JSON."
            )

        if type(
            allowed_incident_origins
        ) is not list:
            raise ProcedureCapabilityRegistryError(
                "allowed_incident_origins "
                "debe ser array JSON."
            )

        applicability = (
            ProcedureApplicability(
                allowed_environments=tuple(
                    allowed_environments
                ),
                allowed_incident_origins=tuple(
                    allowed_incident_origins
                ),
            )
        )

        binding = (
            ProcedureCapabilityBinding(
                procedure_id=raw_binding[
                    "procedure_id"
                ],
                procedure_version=raw_binding[
                    "procedure_version"
                ],
                step_id=raw_binding[
                    "step_id"
                ],
                capability_id=raw_binding[
                    "capability_id"
                ],
                applicability=applicability,
            )
        )

        if not catalog.contains(
            binding.procedure_id,
            binding.procedure_version,
        ):
            raise ProcedureCapabilityRegistryError(
                "La identidad exacta del "
                "procedimiento no existe "
                "en ProcedureCatalog."
            )

        if not catalog.contains_step(
            binding.procedure_id,
            binding.procedure_version,
            binding.step_id,
        ):
            raise ProcedureCapabilityRegistryError(
                "El step exacto no existe "
                "en ProcedureCatalog."
            )

        bindings.append(
            binding
        )

    return ProcedureCapabilityRegistry(
        capability_registry=(
            capability_registry
        ),
        bindings=bindings,
    )


def build_default_procedure_capability_registry(
) -> ProcedureCapabilityRegistry:
    """
    Construye el registry default desde
    configuración source-packaged.

    Autoridades:

    - Procedure Catalog:
      procedure_id + version + step;
    - Capability Registry:
      capability_id;
    - binding manifest:
      asociación y applicability.

    No existe selección mediante LLM,
    fuzzy matching, alias ni fallback.
    """

    return load_procedure_capability_bindings(
        DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH,
        catalog=(
            build_default_procedure_catalog()
        ),
        capability_registry=(
            build_default_capability_registry()
        ),
    )
