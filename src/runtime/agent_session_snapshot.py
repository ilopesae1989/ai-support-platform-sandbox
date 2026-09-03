from __future__ import annotations

import json

from agent_framework import AgentSession


class AgentSessionSnapshotError(
    ValueError
):
    pass


_REQUIRED_SNAPSHOT_KEYS = {
    "type",
    "session_id",
    "service_session_id",
    "state",
}


def encode_agent_session_snapshot(
    session,
) -> str:
    if type(session) is not AgentSession:
        raise TypeError(
            "session debe ser exactamente AgentSession."
        )

    try:
        snapshot = session.to_dict()

        return json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

    except (
        TypeError,
        ValueError,
        KeyError,
    ) as exc:
        raise AgentSessionSnapshotError(
            "AgentSession no puede serializarse "
            "como snapshot JSON durable."
        ) from exc


def decode_agent_session_snapshot(
    payload,
) -> AgentSession:
    if not isinstance(
        payload,
        str,
    ):
        raise TypeError(
            "payload debe ser str."
        )

    if (
        not payload
        or not payload.strip()
        or payload != payload.strip()
    ):
        raise AgentSessionSnapshotError(
            "payload debe ser un string JSON "
            "exacto no vacío."
        )

    try:
        snapshot = json.loads(
            payload
        )
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise AgentSessionSnapshotError(
            "payload no contiene JSON válido."
        ) from exc

    if not isinstance(
        snapshot,
        dict,
    ):
        raise AgentSessionSnapshotError(
            "snapshot debe ser un objeto JSON."
        )

    if set(snapshot) != _REQUIRED_SNAPSHOT_KEYS:
        raise AgentSessionSnapshotError(
            "snapshot debe contener exactamente "
            "el contrato AgentSession durable."
        )

    if snapshot.get(
        "type"
    ) != "session":
        raise AgentSessionSnapshotError(
            "snapshot type debe ser session."
        )

    session_id = snapshot.get(
        "session_id"
    )

    if (
        not isinstance(
            session_id,
            str,
        )
        or not session_id
        or not session_id.strip()
        or session_id != session_id.strip()
    ):
        raise AgentSessionSnapshotError(
            "snapshot session_id debe ser "
            "un string exacto no vacío."
        )

    state = snapshot.get(
        "state"
    )

    if not isinstance(
        state,
        dict,
    ):
        raise AgentSessionSnapshotError(
            "snapshot state debe ser un mapping."
        )

    try:
        restored = AgentSession.from_dict(
            snapshot
        )
    except (
        TypeError,
        ValueError,
        KeyError,
    ) as exc:
        raise AgentSessionSnapshotError(
            "snapshot AgentSession no puede restaurarse."
        ) from exc

    if type(restored) is not AgentSession:
        raise AgentSessionSnapshotError(
            "snapshot no restauró AgentSession exacta."
        )

    return restored
