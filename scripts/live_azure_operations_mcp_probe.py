import asyncio
import json

from src.agents.catalog import (
    AgentKey,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def serialize_value(
    value,
):
    """
    Serialización defensiva únicamente para
    inspección del probe LIVE.

    No forma parte del contrato productivo.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): serialize_value(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            serialize_value(
                item
            )
            for item
            in value
        ]

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(
        model_dump
    ):
        try:
            return serialize_value(
                model_dump(
                    mode="python"
                )
            )
        except Exception:
            pass

    as_dict = getattr(
        value,
        "as_dict",
        None,
    )

    if callable(
        as_dict
    ):
        try:
            return serialize_value(
                as_dict()
            )
        except Exception:
            pass

    data = getattr(
        value,
        "__dict__",
        None,
    )

    if isinstance(
        data,
        dict,
    ):
        return {
            str(key): serialize_value(
                item
            )
            for key, item
            in data.items()
            if not str(
                key
            ).startswith(
                "_"
            )
        }

    return repr(
        value
    )


def inspect_response(
    response,
) -> None:
    """
    Inspecciona la respuesta NATIVA de Agent Framework.

    No aprueba MCP.
    No ejecuta una segunda llamada.
    """

    print(
        "\n"
        "========================================"
    )

    print(
        "NATIVE RESPONSE TYPE"
    )

    print(
        "========================================"
    )

    print(
        type(
            response
        )
    )

    print(
        "\n"
        "========================================"
    )

    print(
        "TOP LEVEL ATTRIBUTES"
    )

    print(
        "========================================"
    )

    for attribute_name in (
        "id",
        "response_id",
        "text",
        "messages",
        "output",
        "items",
        "contents",
        "raw_response",
    ):
        value = getattr(
            response,
            attribute_name,
            None,
        )

        print(
            f"{attribute_name}: "
            f"{serialize_value(value)}"
        )

    print(
        "\n"
        "========================================"
    )

    print(
        "FULL SERIALIZABLE VIEW"
    )

    print(
        "========================================"
    )

    serialized = (
        serialize_value(
            response
        )
    )

    try:
        print(
            json.dumps(
                serialized,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    except Exception:
        print(
            serialized
        )

    print(
        "\n"
        "========================================"
    )

    print(
        "MCP APPROVAL SEARCH"
    )

    print(
        "========================================"
    )

    serialized_text = (
        json.dumps(
            serialized,
            ensure_ascii=False,
            default=str,
        )
    )

    if (
        "mcp_approval_request"
        in serialized_text
    ):
        print(
            "MCP_APPROVAL_REQUEST_FOUND"
        )
    else:
        print(
            "NO_MCP_APPROVAL_REQUEST_STRING_FOUND"
        )


async def main() -> None:
    agents = (
        FoundryAgents()
    )

    definition = (
        agents.get_definition(
            AgentKey.AZURE_OPERATIONS
        )
    )

    print(
        "========================================"
    )

    print(
        "AZURE OPERATIONS LIVE MCP PROBE"
    )

    print(
        "========================================"
    )

    print(
        f"Agent: {definition.name}"
    )

    print(
        f"Version: {definition.version}"
    )

    print(
        f"Subscription: {SUBSCRIPTION_ID}"
    )

    prompt = f"""
Ejecuta exclusivamente una operación Azure de SOLO LECTURA.

Procedimiento autorizado:
NTTSY-SBX-AZ-001

Versión:
v1.0

Objetivo autorizado:
obtener la lista de Resource Groups de la suscripción.

Operation domain:
azure

Operation kind:
read

Target resource:
subscription

Subscription ID autorizado:
{SUBSCRIPTION_ID}

Restricciones obligatorias:

- No crear recursos.
- No modificar recursos.
- No eliminar recursos.
- No iniciar ni detener recursos.
- No cambiar RBAC.
- No cambiar permisos.
- No cambiar de suscripción.
- No ampliar el scope.
- No ejecutar ninguna operación distinta
  de consultar/listar Resource Groups.
- Si MCP requiere aprobación, NO asumas
  que está concedida automáticamente.

Devuelve el resultado de la consulta o la solicitud
de aprobación MCP necesaria para realizar exactamente
esta operación.
""".strip()

    print(
        "\nCalling Azure Operations v11..."
    )

    response = (
        await agents.run_azure_operations(
            prompt
        )
    )

    inspect_response(
        response
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )