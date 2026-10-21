# F27 B02 2.6 — Configuración de la binding READ

## Perfil exacto

El perfil `azure-resource-group-list-sbx-v1` materializa la selección revisada
de `azure.resource_group.list` mediante los contratos existentes de Python.

| Elemento | Valor fijado |
| --- | --- |
| Capability | `azure.resource_group.list` |
| Rol | `AgentKey.AZURE_OPERATIONS` |
| Agente | `agent-azure-operations-rg-list-sbx` |
| Versión | `1` |
| Dominio / tipo | `azure` / `READ` |
| Acción canónica | `OperationAction.RESOURCE_GROUP_LIST` |
| Servidor MCP | `azure-mcp-operations-sbx` |
| Herramienta | `group_list` |
| Aprobación técnica MCP | `always` |
| Parámetro gobernado | `subscription_id` |
| Argumento MCP | `subscription`, vinculado a `subscription_id` |

La capability y la autoridad MCP se obtienen de sus registros canónicos. No se
crean versiones paralelas de esos contratos. Los valores concretos de los
parámetros pertenecen a la solicitud admitida por el runtime y a PreCallSecurity.
La configuración no contiene una subscription ni concede acceso a recursos.

La definición publicada v1 revisada en 2.5 acredita la conexión
`azure-mcp-operations-sbx` y el servidor
`https://azure-mcp-operations-server.mangopond-c98bda59.northeurope.azurecontainerapps.io/`.
El builder selecciona esa versión; no vuelve a consultar la definición ni
certifica remotamente conexión, identidad, RBAC o estado actual. La evidencia
de revisión del agente sigue perteneciendo al expediente de 2.5.

## Configuración explícita y ejemplo local

El consumidor recibe estas dos entradas exactas:

```text
FOUNDRY_CAPABILITY_BINDING_PROFILE=azure-resource-group-list-sbx-v1
FOUNDRY_PROJECT_ENDPOINT=https://aif-icenter-sbx-eus2.services.ai.azure.com/api/projects/aifproj-icenter-sbx
```

Este ejemplo sólo construye y resuelve objetos locales. No inicia un agente,
solicita credenciales, llama Azure ni aprueba MCP:

```python
from src.config.foundry_capability_bindings import (
    build_capability_foundry_agent_binding_registry,
)

environment = {
    "FOUNDRY_CAPABILITY_BINDING_PROFILE": "azure-resource-group-list-sbx-v1",
    "FOUNDRY_PROJECT_ENDPOINT": (
        "https://aif-icenter-sbx-eus2.services.ai.azure.com/"
        "api/projects/aifproj-icenter-sbx"
    ),
}
registry = build_capability_foundry_agent_binding_registry(environment)
binding = registry.get("azure.resource_group.list")
assert binding.agent_definition.name == "agent-azure-operations-rg-list-sbx"
assert binding.agent_definition.version == "1"
assert binding.require_approval == "always"
```

La ausencia de `FOUNDRY_CAPABILITY_BINDING_PROFILE` produce un registro vacío
nuevo. Una clave presente con valor vacío, `None`, otro perfil o variaciones de
espacios/mayúsculas se rechaza. El perfil admitido exige el endpoint exacto del
proyecto revisado; no se normalizan endpoints ni se acepta `latest` como perfil.

`build_production_application()` materializa esta configuración antes de
construir dependencias proveedoras. Una inyección explícita mediante
`capability_foundry_agent_binding_registry` prevalece y conserva su identidad,
incluido un registro vacío. El catálogo general `agent-azure-operations-sbx:13`
y su variable de versión no seleccionan este perfil dedicado.

## Consumo en el recorrido y límites

La raíz de aplicación entrega el mismo registro a la composición Teams, el
bootstrap productivo, el bootstrap Teams, el workflow y la composición Azure.
El executor resuelve la binding y compara la solicitud con la capability y la
autoridad MCP antes de consumir el claim de despacho. La misma
`workflow_factory` se comparte entre el handler humano y el worker de
continuación.

La binding sólo selecciona un agente. La aprobación humana HITL, la aprobación
técnica MCP, la admisión de procedimientos, PreCallSecurity y la evidencia de
resultado siguen gobernándose en sus fronteras existentes. El perfil no añade
procedimientos READ al catálogo ni inicia una prueba PENDING.

## T06 — Punto del consumidor desplegable

El `Dockerfile` inicia `python -m src.production_main`. Ese entrypoint copia
`os.environ` y lo entrega a `build_production_application()`. Por tanto, el
punto de configuración que utilizará ese consumidor es el environment del
contenedor de la aplicación con las dos entradas indicadas arriba.

La infraestructura del snapshot declara el host en
`infra/container-apps/application-host.bicep`, invocado desde
`infra/application-foundation.bicep`. Actualmente transmite
`FOUNDRY_PROJECT_ENDPOINT` y `FOUNDRY_MANAGED_IDENTITY_CLIENT_ID`, pero **no
transmite `FOUNDRY_CAPABILITY_BINDING_PROFILE`**. Los dos Bicep y su contrato de
42 parámetros permanecen intactos en 2.6.

Esto identifica el punto de consumo en código y la configuración que falta en
el despliegue. No acredita el environment, la imagen ni la revisión actualmente
desplegados. La activación en el consumidor y la demostración integral de su
consumo permanecen vinculadas a G6; este cambio no ejecuta un despliegue.
