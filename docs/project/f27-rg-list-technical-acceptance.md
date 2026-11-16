# F27-B06 — Contrato técnico de RG List

Estado: contrato e implementación local; instalación de esta ampliación y asociación auténtica de B06-T03 pendientes. Objetivo F48 PRODUCTIVE MVP CLOSED, rector 224 × 63 sin cambios. Este documento no añade tareas.

## Qué satisface el procedimiento

La operación gobernada es `azure.resource_group.list`, dominio `azure`, tipo `read`, acción `resource_group_list` y destino `subscription`. El registro READ existente aporta servidor, herramienta y traducción exacta de `subscription_id` a `subscription`. No se obtiene autoridad del texto del agente ni del resultado MCP.

Python exige conjuntamente:

1. Estado autoritativo `WAITING_VALIDATION`, resultado operacional registrado e inexistencia de verificación previa. El resultado presentado debe coincidir íntegramente con el registrado y con workflow, aprobación, alerta, correlación, conversación, procedimiento/versión, paso, destino y parámetros. Se mantienen las validaciones existentes de `OperationResult` y del gate.
2. Identidad canónica RG List y política HITL coherentes entre paso y resultado. Las rutas legacy sin esa capability conservan su contrato; omitir identidad en un paso RG List no permite eludir la guarda.
3. Invocación completada (`success=True`), resultado técnico derivado `True`, sin error declarado y evidencia estructurada concordante. `success` del executor, HTTP/MCP 200 y juicio cognitivo `satisfied` son señales distintas.
4. Una llamada MCP y su único resultado, mismo identificador, herramienta `group_list`, servidor del registro READ, argumentos exactamente autorizados y ninguna llamada function adicional. El único parámetro resuelto es `subscription_id`, con formato GUID. Las identidades de la evidencia y de `OperationResult` coinciden por el modelo existente.
5. Un único cuerpo de resultado admitido: objeto, JSON de ese objeto o un único elemento MCP `type=text` con JSON. El JSON rechaza claves duplicadas, constantes no finitas y envoltorios ambiguos. No interpreta lenguaje natural. Límite explícito de 1 MB de texto, profundidad de envoltorio cuatro y 10.000 entradas; excederlos bloquea, nunca trunca para aceptar.
6. `status` entero exactamente 200, sin error ni `isError`, y `results.groups` como lista. Un array vacío expresa inventario vacío y puede satisfacer el contrato; un campo ausente no es equivalente. Cualquier `nextLink` no vacío impide aceptar un resultado parcial.
7. Cada entrada contiene `name`, `id` y `location` como textos no vacíos. El ID debe ser literalmente `/subscriptions/{subscription_id}/resourceGroups/{name}`; no se corrige ni normaliza para aceptar otra suscripción o nombre. Se rechazan IDs duplicados, incluidos los que difieren sólo por capitalización. Otros metadatos de RG no conceden autoridad ni se interpretan como instrucciones.

La forma `status/results/groups` procede del contrato y fixtures históricos del repositorio, incluidos los adaptadores de salida MCP. Microsoft Learn documenta que `group_list` devuelve una lista de grupos con nombre, ID y ubicación. La forma observada en otro artefacto debe reconciliarse antes de ampliar este contrato.

## Salidas deterministas

| Evidencia | Salida |
| --- | --- |
| Fallo, timeout, desconocido, ausencia de evidencia o contenido inválido | `BLOCKED`, error `RG_LIST_TECHNICAL_ACCEPTANCE_NOT_MET`; conserva resultado y propuesta cognitiva. |
| Contenido favorable de otra llamada, herramienta, servidor, suscripción o argumentos | `BLOCKED`; no avance, resolución ni retry implícito. |
| Sustitución de identidad, paso, resultado registrado o replay | Rechazo por las guardas existentes antes de una transición válida. |
| Resultado completo conforme y propuesta válida | La transición normal del procedimiento; `continue` en el último paso sólo resuelve cuando la condición técnica se cumple. |

El gate no concede aprobación humana ni MCP, no despacha herramientas, no reintenta y no llama a Azure. `BLOCKED` conserva contador de retry y posición del paso.

## Qué no demuestra esta validación

La igualdad de campos no autentica al productor. Estos casos prueban lógica local sobre evidencia estructurada; no certifican JWT, identidad efectiva, selección de versión del servicio, firma, custodia, cobertura del sensor, persistencia SQL/WORM ni integridad de un inventario real. B06-T03 mantiene pendiente la asociación auténtica instalada. H10/H11 y B10 siguen requiriendo sus recibos propios; una fixture no los sustituye.

Tampoco se demuestra que Azure no omitió un recurso. El contrato comprueba contenido recibido, identidad autorizada y ausencia de paginación incompleta declarada. La suficiencia del productor y del alcance observado pertenece a la evidencia operacional.

## Evidencia y estado

R4 se aplicó una vez en Windows con 25 postimágenes verificadas, preservando HEAD/rama/índice. Datos públicos SHA256 `64152a6a4c8bf2ff166872bbf24237d24565dfe6a35058333ad527b1f66e3a15`; recibo SHA256 `ed9618fcc50347ae80c8c4ff0078d5f50affeebb16c36d5abc5bf5b4abe9f7ca`. R4 rechaza los negativos técnicos iniciales, pero un `status=200` sin contenido aún podía resolver; esta ampliación corrige ese hueco de B06-T02/T03.

Se añaden casos adversariales a través del gate y runtime reales: resultados desnudos, grupos mal formados, suscripción/nombre/ID sustituidos, duplicados, paginación, error contradictorio, JSON ambiguo, herramienta/servidor/argumentos distintos, llamadas múltiples y propuestas de avance/retry. El expediente de entrega contiene resultados focales y de regresión separados, con entorno y hashes. La FULL final B07/H13 sigue pendiente de la referencia final de todas las integraciones.

## Fuentes consultadas el 10/11/2026

- [Azure MCP: resource groups](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/resource-group).
- [MCP en Foundry: aprobación y herramientas permitidas](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol).
- [Autorización del endpoint del agente](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-endpoint-authorization).

Las comprobaciones adicionales son el contrato del procedimiento de este proyecto, no una garantía de Microsoft sobre esta instalación.
