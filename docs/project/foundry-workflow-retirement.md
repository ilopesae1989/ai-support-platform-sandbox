# Foundry workflows: retirada y decisión para el producto

Revisión del 17/11/2026, solicitada por el usuario durante E3-P5.
Base publicada: `a54050897f354acae94f9ed3dd25452f5f38ec3a`.

## Alcance de la retirada

Microsoft anuncia la retirada del diseñador visual y la ejecución de workflows
en el portal Foundry para el **1 de diciembre de 2026**. La guía recomienda
Microsoft Agent Framework para orquestación mediante código; también describe
Logic Apps para diseño visual y A2A para delegaciones sencillas entre agentes.
No es un anuncio de retirada de `agent_framework.WorkflowBuilder`.

La documentación de Agent Framework mantiene la API de grafos con ejecutores,
aristas, eventos y checkpoints. La alternativa funcional Python se documenta
como experimental; este proyecto no necesita cambiar a ella por este aviso.

## Evidencia del repositorio

| Archivo revisado | Función observada |
| --- | --- |
| `requirements-runtime.txt`, `requirements-dev.txt` | Versiones fijadas: core 1.13.0 y foundry 1.10.4 |
| `src/workflows/incident_resolution/workflow.py` | Importa `WorkflowBuilder` de `agent_framework` y construye el grafo en Python |
| `src/workflows/incident_resolution/composition.py` | Crea el workflow desde dependencias de confianza inyectadas por el host |
| `src/channels/teams/bootstrap.py` | Compone la fábrica anterior y los almacenes de continuación |
| `src/agents/foundry_agents.py` | Adaptadores `FoundryAgent` hacia agentes especializados versionados; no mantiene el estado durable del workflow |
| `infra/container-apps/Dockerfile.f27-core`, `application-host.bicep` | Host de aplicación en Container Apps; arranque `python -m src.production_main` |

La búsqueda dirigida en `src`, `agent-definitions`, `infra`, `scripts` y
`.github` no encontró definiciones `.workflow.yaml` ni tipos `kind: workflow`
o `DeclarativeWorkflow`. Es una comprobación de dependencias en el código,
no una lectura semántica integral ni un inventario de recursos desplegados.
No se consultó Azure en esta revisión. Los recursos creados sólo en el portal
y sus consumidores continúan sin conciliación LIVE actual.

## Decisión y justificación

1. Mantener Python y los grafos de Microsoft Agent Framework en el core.
   El aviso recomienda esa familia de runtime y el código ya usa esa separación.
   No cambiar SDK ni formato de checkpoints dentro de una corrección de pruebas.
2. Mantener Foundry para los agentes especializados y MCP para herramientas
   gobernadas. La retirada del diseñador no acredita la retirada de esos agentes.
3. Conservar A2A como frontera opcional entre agentes remotos. Sustituir el grafo
   por delegaciones A2A no resolvería por sí solo las aprobaciones, la propiedad
   de intentos o la recuperación durable que estamos implementando.
4. No introducir LangChain/LangGraph por este aviso. Serían alternativas a evaluar
   por requisitos propios; una sustitución exigiría revalidar ejecución, HITL,
   checkpoints y adaptadores. La retirada no ofrece motivo para asumir ese coste.
5. Para F40/F46, distribuir una versión del core y configuración de cada cliente
   con referencias de agentes fijadas. El manifiesto y la aceptación del cliente
   deben excluir dependencias del diseñador y la ejecución en portal retirados.
   Esta regla documental no acredita todavía un control automatizado en CI.

Antes de cerrar un despliegue, contrastar su inventario Foundry y consumidores.
Si aparece un workflow del portal, exportar su definición y registrar una
migración explícita con equivalencia de ramas, HITL, estado y consumidores antes
de retirarlo. No desplegar un Hosted Agent ni borrar recursos por inferencia.
La guía ofrece Hosted Agents como destino; el producto actual usa su propio
host y esta revisión no autoriza ni obliga a cambiar ese despliegue.

## Fuentes oficiales

Consultadas el 17/11/2026:

- [Foundry: anuncio y guía de migración](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/workflow#migration-guide).
- [Foundry Toolkit: migración; orquestación en código no afectada](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/vs-code-agents-workflow-low-code).
- [Agent Framework: conceptos y APIs de workflows](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/).
- [Agent Framework: WorkflowBuilder y ejecución](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows).

Este análisis complementa la decisión previa; no afirma que la fecha de retirada
estuviera ya documentada. No cierra F27 LIVE, F30/F31, F40, F46 ni la entrega 3.
