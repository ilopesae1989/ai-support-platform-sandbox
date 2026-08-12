from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from .workflow import (
    ApprovalRequest,
)


class PendingApprovalCorrelation(
    BaseModel
):
    """
    Correlación técnica necesaria para reanudar
    exactamente una solicitud HITL pendiente.

    approval_id:
        identidad de negocio/gobierno de la
        aprobación.

    workflow_id:
        identidad del workflow gobernado.

    request_id:
        identidad técnica asignada por
        Microsoft Agent Framework al
        RequestInfoEvent.

    checkpoint_id:
        checkpoint exacto desde el que puede
        restaurarse la ejecución.

    No contiene autoridad operacional.

    La operación aprobable continúa viviendo
    exclusivamente en el ApprovalRequest y en
    el estado/checkpoint gobernado.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    approval_id: str
    workflow_id: str

    request_id: str
    checkpoint_id: str

    @field_validator(
        "approval_id",
        "workflow_id",
        "request_id",
        "checkpoint_id",
    )
    @classmethod
    def validate_exact_nonempty_string(
        cls,
        value: str,
    ) -> str:
        if not value:
            raise ValueError(
                "El identificador no puede "
                "estar vacío."
            )

        if not value.strip():
            raise ValueError(
                "El identificador no puede "
                "contener únicamente espacios."
            )

        if value != value.strip():
            raise ValueError(
                "El identificador no puede "
                "contener espacios al inicio "
                "o al final."
            )

        return value


def build_pending_approval_correlation(
    *,
    request: ApprovalRequest,
    request_id: str,
    checkpoint_id: str,
) -> PendingApprovalCorrelation:
    """
    Construye la correlación usando la identidad
    gobernada del ApprovalRequest original.

    El caller NO puede proporcionar de nuevo:

        approval_id
        workflow_id

    evitando que esos valores se reconstruyan
    desde Teams o cualquier otro canal.
    """

    if not isinstance(
        request,
        ApprovalRequest,
    ):
        raise TypeError(
            "request debe ser ApprovalRequest."
        )

    return PendingApprovalCorrelation(
        approval_id=(
            request.approval_id
        ),

        workflow_id=(
            request.workflow_id
        ),

        request_id=(
            request_id
        ),

        checkpoint_id=(
            checkpoint_id
        ),
    )
class ApprovalCorrelationError(
    ValueError
):
    pass


class ApprovalCorrelationNotFoundError(
    ApprovalCorrelationError
):
    pass


class DuplicateApprovalCorrelationError(
    ApprovalCorrelationError
):
    pass


class ApprovalCorrelationRegistry:
    """
    Índice determinista de correlaciones HITL.

    Esta clase NO constituye todavía el storage
    durable productivo.

    Define las invariantes que cualquier storage
    posterior deberá respetar:

    - un approval_id identifica una única request;
    - un request_id pertenece a una única approval;
    - no existe fallback;
    - no existe fuzzy matching;
    - no existe resolución mediante LLM.
    """

    def __init__(
        self,
    ) -> None:
        self._by_approval_id: dict[
            str,
            PendingApprovalCorrelation,
        ] = {}

        self._by_request_id: dict[
            str,
            PendingApprovalCorrelation,
        ] = {}

    def register(
        self,
        correlation: PendingApprovalCorrelation,
    ) -> None:
        if not isinstance(
            correlation,
            PendingApprovalCorrelation,
        ):
            raise ApprovalCorrelationError(
                "Sólo pueden registrarse "
                "PendingApprovalCorrelation."
            )

        if (
            correlation.approval_id
            in self._by_approval_id
        ):
            raise (
                DuplicateApprovalCorrelationError(
                    "approval_id ya registrado: "
                    f"{correlation.approval_id!r}."
                )
            )

        if (
            correlation.request_id
            in self._by_request_id
        ):
            raise (
                DuplicateApprovalCorrelationError(
                    "request_id ya registrado: "
                    f"{correlation.request_id!r}."
                )
            )

        self._by_approval_id[
            correlation.approval_id
        ] = correlation

        self._by_request_id[
            correlation.request_id
        ] = correlation

    def get_by_approval_id(
        self,
        approval_id: str,
    ) -> PendingApprovalCorrelation:
        correlation = (
            self._by_approval_id.get(
                approval_id
            )
        )

        if correlation is None:
            raise (
                ApprovalCorrelationNotFoundError(
                    "No existe correlación para "
                    "approval_id="
                    f"{approval_id!r}."
                )
            )

        return correlation

    def get_by_request_id(
        self,
        request_id: str,
    ) -> PendingApprovalCorrelation:
        correlation = (
            self._by_request_id.get(
                request_id
            )
        )

        if correlation is None:
            raise (
                ApprovalCorrelationNotFoundError(
                    "No existe correlación para "
                    "request_id="
                    f"{request_id!r}."
                )
            )

        return correlation

    def count(
        self,
    ) -> int:
        return len(
            self._by_approval_id
        )