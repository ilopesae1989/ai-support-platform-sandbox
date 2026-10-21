# AI Support Platform

Plataforma de soporte IT en desarrollo dentro del proyecto **«Creación de agentes»**. El contrato técnico incluye **AI, AI-103 y agentes**.

## Objetivo final

**F48 — PRODUCTIVE MVP CLOSED**: entregar una plataforma real reutilizable, gobernada, segura, durable, auditable, mantenible, operable por otro equipo y desplegable por cliente. El core común debe poder incorporar fuentes, dominios, capacidades, conocimiento y canales mediante contratos y configuración explícitos.

## Autoridad y gobierno

- El LLM interpreta y propone. Python gobierna procedimientos, identidad, capacidades, parámetros, política, aprobaciones, despacho, evidencia y transiciones.
- El humano autoriza cuando la política lo exige. La aprobación humana HITL y la aprobación técnica MCP se verifican en fronteras distintas.
- MCP ejecuta operaciones admitidas. Los resultados y su evidencia correlacionada determinan lo que puede afirmarse sobre una ejecución.
- Teams proporciona transporte y experiencia del operador. Un mensaje, un ticket, una sesión conversacional o un checkpoint no concede autoridad para ejecutar o repetir operaciones.
- La sandbox vigente prohíbe operaciones destructivas. Esta restricción local no define por sí sola la política de futuros clientes.
- Una capability READ con `hitl_required=False` conserva la política global de sandbox que corresponda; no permite omitir sus controles humanos.

## Estado del proyecto — corte documental de 21/10/2026

La fase activa es **F27.3**, bloque **F27-B02**, subfase **2.7**. El [plan por fases y tareas](docs/project/roadmap-f27-f48.md) conserva las dependencias, criterios de cierre y siguiente acción. Sus estados son del alcance descrito en cada tarea.

| Ámbito | Estado acreditado |
| --- | --- |
| F27-B01 | Reconciliación focal de interfaces publicada en `76fabdc52f38c462234c62b111cf4362de2d337f`. |
| F27-B02, 2.1–2.5 | Inventario, contrato READ, mapa de conexión/identidades, transporte offline y candidata revisada cerrados en sus alcances documentados. |
| F27-B02, 2.6 | Binding explícita y pruebas focales completadas; 127 casos focales Windows conservados como evidencia de ese cambio. |
| F27-B02, 2.7-T01 y 2.7-T02 | Preparación del runner y comprobación offline completadas. La verificación R3 Windows termina en `OFFLINE_PROCESS_FOCAL_PASSED`. |
| F27-B02, resto de 2.7 y 2.8–2.10 | Pendientes: requisitos del ensayo, pausa MCP nativa, continuación y cierre del expediente. |
| F27-B03–B11, G1–G6 | Pendientes en los alcances de catálogo, consumidor, backend, validación y cierre que fija el plan. |
| F28–F48 | Planificadas; aceptación productiva pendiente. |

Las pruebas offline usan respuestas sintéticas y transporte controlado. El expediente conserva también las lecturas y actuaciones históricas de Foundry, incluida la creación y revisión de la candidata READ. Ninguno de esos hechos certifica por sí solo el estado actualmente desplegado, una operación MCP real, el consumidor productivo o el E2E. Los informes anteriores conservan sus resultados originales, incluidos los STOP; las revisiones posteriores documentan sus conclusiones por separado.

### Configuración READ disponible en código

La [configuración de binding Foundry](docs/foundry/capability-binding-configuration.md) materializa un perfil exacto y opcional para `azure.resource_group.list`, con versión fijada, herramienta `group_list` y aprobación MCP `always`. La ausencia de perfil mantiene un registro vacío. La configuración inválida se rechaza antes de construir dependencias proveedoras.

El punto de consumo está identificado en `src.production_main` y `build_production_application()`. La infraestructura actual del repositorio aún no entrega `FOUNDRY_CAPABILITY_BINDING_PROFILE` al contenedor, y el catálogo de procedimientos aún no instala el caso RG List. Esos trabajos permanecen en F27-B03/F27-B04 y en la demostración del recorrido integrado. El alcance preparado de este checkpoint es de código y documentación; esta revisión no ejecuta cambios de despliegue.

### Validación y continuidad

Las pruebas focales, la comprobación SDK offline, una FULL NON-LIVE y una ejecución LIVE tienen criterios de aceptación diferentes. Se conserva la evidencia de cada una con su código, configuración y entorno. Una prueba focal correcta no cierra F27 ni permite avanzar automáticamente a F28.

La siguiente tarea de producto se toma siempre del [plan vigente](docs/project/roadmap-f27-f48.md). Un checkpoint Git conserva el trabajo y facilita el cambio de chat; su publicación requiere observar el resultado del push. El contenido de este README no afirma que un push, un despliegue o una ejecución pendiente ya hayan ocurrido.

## Referencias oficiales Microsoft

Consulta registrada: **21/10/2026**. Las referencias describen contratos del proveedor; la evidencia del proyecto acredita qué se ha ejecutado en esta instalación.

- [Uso de herramientas MCP en Microsoft Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol). Referencia del flujo de solicitud/aprobación MCP. Fecha de actualización observada en la consulta: 08/10/2026.
- [Migración de aplicaciones de agentes](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/migrate-agent-applications). Referencia para distinguir APIs, modelos de agentes y rutas de invocación. Fecha de actualización observada en la consulta: 21/07/2026.

Los ejemplos de otra API o versión no autorizan una actualización automática de dependencias ni sustituyen la comprobación del transporte realmente instalado.

## Diseño inicial conservado como historial

El contenido siguiente se preserva íntegro desde el README anterior. Describe el diseño inicial de sandbox y sus observaciones de aquel momento. **No representa la configuración actual ni una nueva decisión vinculante**: presupuesto, regiones, componentes, topología y estado de recursos requieren la evidencia del expediente correspondiente. Por ejemplo, la afirmación histórica de recursos aún no desplegados no es el estado actual que certifica este documento.

<details>
<summary>README original — diseño inicial histórico</summary>

# AI Support Platform Sandbox

Sandbox técnica para desplegar y validar una plataforma multiagente de soporte basada en Microsoft Foundry y servicios Azure.

## Datos base

- Cliente: icenter
- Entorno: sandbox
- Región primaria: westeurope
- Presupuesto máximo mensual: 250 EUR
- Suscripción: Azure AI Sandbox – iCenter Microsoft
- Microsoft Foundry: Basic Agent Setup
- Interfaz principal: Microsoft Teams
- Repositorio documental: SharePoint Online
- ITSM inicial: ServiceNow
- Human in the loop: obligatorio para todas las operaciones de escritura

## Principios de diseño

- Sin alta disponibilidad.
- Sin red privada.
- Sin Private Endpoints.
- Sin Durable Task Scheduler.
- Durable Functions con Azure Storage.
- Azure AI Search Free condicionado a capacidad.
- Azure SQL Database Basic.
- Service Bus Standard.
- Container Apps Consumption con escala a cero.
- Un modelo de chat compartido.
- Un modelo de embeddings.
- Azure MCP Server oficial de Microsoft alojado en Azure Container Apps.
- Ningún agente tendrá Owner, Contributor ni User Access Administrator.

## Modelos candidatos aprobados

- Chat: gpt-5-mini
- Versión: 2025-08-07
- Deployment: DataZoneStandard
- Capacidad inicial: 10 K TPM

- Embeddings: text-embedding-3-small
- Versión: 1
- Deployment: DataZoneStandard
- Dimensiones: 768
- Capacidad inicial: 10 K TPM

## Estado actual

- Contexto Azure validado.
- Proveedores registrados.
- Región West Europe validada.
- Cuota de modelos validada.
- Azure AI Search Free estimado como viable con límites.
- Recursos Azure aún no desplegados.

</details>
