from __future__ import annotations

import asyncio
import json

from collections.abc import Mapping

from urllib.request import (
    Request,
    urlopen,
)

from uuid import UUID

from azure.identity.aio import (
    ManagedIdentityCredential,
)


GRAPH_SCOPE = (
    "https://graph.microsoft.com/.default"
)

GRAPH_BASE_URL = (
    "https://graph.microsoft.com/v1.0"
)


class GraphMembershipClientError(
    RuntimeError
):
    pass


def _canonical_uuid(
    *,
    name: str,
    value: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise GraphMembershipClientError(
            f"{name} inválido."
        )

    try:
        parsed = UUID(
            value
        )
    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        raise GraphMembershipClientError(
            f"{name} inválido."
        ) from None

    if str(parsed) != value:
        raise GraphMembershipClientError(
            f"{name} inválido."
        )

    return value


class UrllibGraphJsonTransport:
    async def post_json(
        self,
        *,
        url: str,
        headers: Mapping,
        payload: Mapping,
        timeout_seconds: float,
    ):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._post_json_sync,
                    url=url,
                    headers=headers,
                    payload=payload,
                    timeout_seconds=(
                        timeout_seconds
                    ),
                ),
                timeout=timeout_seconds,
            )
        except Exception:
            raise GraphMembershipClientError(
                "Microsoft Graph transport "
                "failed."
            ) from None

    @staticmethod
    def _post_json_sync(
        *,
        url: str,
        headers: Mapping,
        payload: Mapping,
        timeout_seconds: float,
    ):
        request_headers = dict(
            headers
        )

        request_headers[
            "Content-Type"
        ] = "application/json"

        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode(
            "utf-8"
        )

        request = Request(
            url=url,
            data=body,
            headers=request_headers,
            method="POST",
        )

        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            status = getattr(
                response,
                "status",
                None,
            )

            if status != 200:
                raise RuntimeError(
                    "Microsoft Graph devolvió "
                    "un status inesperado."
                )

            raw = response.read()

        return json.loads(
            raw.decode(
                "utf-8"
            )
        )


class MicrosoftGraphGroupMembershipClient:
    def __init__(
        self,
        *,
        credential: object,
        transport: object,
        timeout_seconds: float = 5.0,
    ):
        if not callable(
            getattr(
                credential,
                "get_token",
                None,
            )
        ):
            raise TypeError(
                "credential debe implementar "
                "get_token()."
            )

        if not callable(
            getattr(
                transport,
                "post_json",
                None,
            )
        ):
            raise TypeError(
                "transport debe implementar "
                "post_json()."
            )

        if (
            not isinstance(
                timeout_seconds,
                (int, float),
            )
            or isinstance(
                timeout_seconds,
                bool,
            )
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds debe ser "
                "positivo."
            )

        self._credential = (
            credential
        )

        self._transport = (
            transport
        )

        self._timeout_seconds = float(
            timeout_seconds
        )

    async def is_transitive_member(
        self,
        *,
        user_object_id: str,
        group_object_id: str,
    ) -> bool:
        user_object_id = _canonical_uuid(
            name="user_object_id",
            value=user_object_id,
        )

        group_object_id = _canonical_uuid(
            name="group_object_id",
            value=group_object_id,
        )

        url = (
            f"{GRAPH_BASE_URL}/users/"
            f"{user_object_id}/"
            "checkMemberGroups"
        )

        try:
            token = await (
                self._credential.get_token(
                    GRAPH_SCOPE
                )
            )

            token_value = getattr(
                token,
                "token",
                None,
            )

            if (
                not isinstance(
                    token_value,
                    str,
                )
                or not token_value
                or not token_value.strip()
                or token_value
                != token_value.strip()
            ):
                raise RuntimeError(
                    "Token Graph inválido."
                )

            response = await (
                self._transport.post_json(
                    url=url,
                    headers={
                        "Authorization": (
                            f"Bearer {token_value}"
                        )
                    },
                    payload={
                        "groupIds": [
                            group_object_id
                        ]
                    },
                    timeout_seconds=(
                        self._timeout_seconds
                    ),
                )
            )

        except GraphMembershipClientError:
            raise

        except Exception:
            raise GraphMembershipClientError(
                "Microsoft Graph membership "
                "evaluation failed."
            ) from None

        if not isinstance(
            response,
            Mapping,
        ):
            raise GraphMembershipClientError(
                "Microsoft Graph devolvió "
                "una respuesta inválida."
            )

        values = response.get(
            "value"
        )

        if not isinstance(
            values,
            list,
        ):
            raise GraphMembershipClientError(
                "Microsoft Graph devolvió "
                "una respuesta inválida."
            )

        for value in values:
            if not isinstance(
                value,
                str,
            ):
                raise GraphMembershipClientError(
                    "Microsoft Graph devolvió "
                    "una respuesta inválida."
                )

            _canonical_uuid(
                name=(
                    "returned_group_object_id"
                ),
                value=value,
            )

        return (
            group_object_id
            in values
        )


def build_managed_identity_graph_membership_client(
    *,
    managed_identity_client_id: str,
    timeout_seconds: float = 5.0,
) -> MicrosoftGraphGroupMembershipClient:
    if (
        managed_identity_client_id
        == "system"
    ):
        credential = (
            ManagedIdentityCredential()
        )

    else:
        client_id = _canonical_uuid(
            name=(
                "managed_identity_client_id"
            ),
            value=(
                managed_identity_client_id
            ),
        )

        credential = (
            ManagedIdentityCredential(
                client_id=client_id
            )
        )

    return MicrosoftGraphGroupMembershipClient(
        credential=credential,
        transport=(
            UrllibGraphJsonTransport()
        ),
        timeout_seconds=timeout_seconds,
    )
