from uuid import uuid4


def create_workflow_id() -> str:
    """
    Identificador único de una ejecución concreta.

    Una misma alerta puede tener varias ejecuciones;
    cada una debe recibir un workflow_id diferente.
    """

    return f"wf-{uuid4()}"


def create_approval_id() -> str:
    """
    Identificador único de una solicitud HITL.

    No sustituye todavía al nonce durable de
    producción.
    """

    return f"apr-{uuid4()}"