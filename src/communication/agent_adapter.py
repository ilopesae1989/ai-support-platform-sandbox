from __future__ import annotations

import json

from pydantic import ValidationError

from .contracts import (
    CommunicationRequest,
    CommunicationResult,
)


class CommunicationAgentAdapterError(
    RuntimeError
):
    pass


class CommunicationAgentAdapter:
    """
    Boundary cognitivo mínimo para transformar una
    solicitud comunicable en contenido de presentación.

    El lifecycle y el contexto permanecen fuera
    de este componente.
    """

    def __init__(
        self,
        *,
        runner: object,
    ) -> None:
        run_method = getattr(
            runner,
            "run",
            None,
        )

        if not callable(run_method):
            raise TypeError(
                "runner debe exponer run()."
            )

        self._runner = runner

    async def run(
        self,
        request: CommunicationRequest,
    ) -> CommunicationResult:
        if type(request) is not CommunicationRequest:
            raise TypeError(
                "request debe ser exactamente "
                "CommunicationRequest."
            )

        response = await self._runner.run(
            request.model_dump_json()
        )

        text = getattr(
            response,
            "text",
            None,
        )

        if (
            not isinstance(
                text,
                str,
            )
            or not text.strip()
        ):
            raise CommunicationAgentAdapterError(
                "El runner no devolvio contenido textual."
            )

        try:
            payload = json.loads(
                text
            )

        except json.JSONDecodeError as exc:
            raise CommunicationAgentAdapterError(
                "El runner no devolvio JSON valido."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise CommunicationAgentAdapterError(
                "La respuesta debe ser un objeto JSON."
            )

        try:
            return CommunicationResult.model_validate(
                payload
            )

        except ValidationError as exc:
            raise CommunicationAgentAdapterError(
                "La respuesta no cumple "
                "CommunicationResult."
            ) from exc