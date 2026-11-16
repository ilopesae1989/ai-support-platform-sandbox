# F46 — Configuración por cliente y autoridad READ

Fecha: 16/11/2026. Entrega 2 del plan de refactorización hasta F48.
Baseline: `a88c79c5f1d2be924c8aed99b8b6d4f1e12163f7`, rama `phase16-wip`.
El operador confirmó esa rama/HEAD y árbol de trabajo limpio en Windows.

Actualización posterior: R2 fue validada en Windows con **3.400 passed,
24 deselected, 3 warnings**, exit code 0, y publicada en
`6d141382a84e22c97e4c461eb869c96d8433ac2e`, rama
`codex/f46-configuracion-clientes`. Se comprobaron los 19 blobs remotos.
JUnit: `F46_R2_WINDOWS_20261116_155350.xml`, SHA256
`b8a8fc2f541480b485906f07d0dbf108fb52a6f81026eae4f84faf04e38695c5`.
R2 sólo asignó un ID corto al caso de entrada de 100.001 caracteres: Windows
rechazaba su ID automático al guardarlo en PYTEST_CURRENT_TEST. La entrada y
su validación se conservaron. Las menciones a Windows pendiente de abajo
describen la preparación inicial; quedan superadas por esta evidencia.
Entrega 2 cerrada en su alcance de código/NON-LIVE; F46 global sigue abierta.
Continúa [Entrega 3 — núcleo y recuperación](e3-core-recovery.md).

## Problema y resultado

El catálogo histórico fija nombres de sandbox. Además, el ejecutor puede
seleccionar el servidor READ aislado mientras la aceptación de RG List vuelve a
`azure-mcp-operations-sbx`. Un resultado correcto del perfil seleccionado acaba
bloqueado por esa discrepancia.

El perfil nuevo inyecta un catálogo completo de ocho roles y publicaciones READ
y WRITE separadas desde configuración del host. Un único registro READ pasa del
workflow a operaciones y a la transición final. Un registro explícitamente vacío
no recupera la autoridad legacy.

El fingerprint de configuración Foundry forma parte del ID del nodo inicial y,
por tanto, de la firma del grafo del SDK. Un checkpoint sólo puede restaurarse
con la misma configuración Foundry. Cambiar cliente/proyecto, agentes, versiones,
conexiones, hosts o el selector de identidad Foundry bloquea la restauración antes
de ejecutar handlers. Esto permite conservar la versión anterior para casos
activos; no implementa una migración automática de esos casos.

## Trazabilidad y límites

| ID | Trabajo en este paquete | Alcance del estado |
| --- | --- | --- |
| F46-T01/T02 | Variaciones de catálogo/publicaciones y contrato de configuración | Diseño concretado para Foundry; la arquitectura completa por cliente sigue abierta |
| F46-T03 | Configuración tipada, inyección y aislamiento de selección | Implementado en candidato de código |
| F46-T04 | A/B, negativos y compatibilidad de checkpoints | Pruebas sintéticas NON-LIVE; instalación/aislamiento efectivo pendientes |
| F40-T03/T04 | Nuevos escenarios y regresión | Resultado registrado más abajo; verificación Windows pendiente |
| F27-B03/B04/B06 | Coherencia entre selección y aceptación | Contribución local; no cierra F27 ni sus gates LIVE |

Se conservan todos los IDs F27–F48. F27 LIVE permanece pausada. No se publican
agentes, no se invocan modelos/MCP ni se modifica Azure mediante este paquete.
Las conexiones/URLs declaradas necesitan readback de la publicación efectiva;
el parser no verifica sus herramientas, identidades, permisos ni aprobación remota.

La prueba A/B demuestra configuración independiente y rechazo de un servidor ajeno;
no acredita aislamiento Azure entre tenants ni acceso real a datos de clientes.
La firma cubre esta configuración Foundry y su selector de identidad, no sustituye
la autoridad de recursos, políticas, SQL, aprobación o evidencias existente.
Las sesiones remotas y la recuperación durante un efecto incierto siguen en la
entrega 3. No se restaura una sesión Foundry completa sólo con este fingerprint.

## Contrato de configuración

`FOUNDRY_DEPLOYMENT_JSON` activa el perfil completo. Es configuración de confianza
del host; nunca se construye desde un ticket, documento, mensaje o salida de agente.
`FOUNDRY_PROJECT_ENDPOINT` debe coincidir exactamente con el documento.
El resto de configuración de identidad, Teams, SQL, procedimientos y evidencias
conserva sus contratos existentes.

| Parte | Regla | Motivo |
| --- | --- | --- |
| `schema_version` | Exactamente `1.0` | Rechazar contratos desconocidos |
| `project_endpoint` | HTTPS y ruta `/api/projects/<proyecto>` | Resolver un proyecto concreto |
| `agents` | Ocho claves exactas de `AgentKey`; nombre y versión por rol | Evitar completar roles con defaults del sandbox |
| Versiones | Strings numéricos positivos, sin alias `latest` | Fijar la publicación seleccionada |
| `read` | Agente, versión, conexión, URL raíz y etiqueta propios | Mantener separada la lectura gobernada |
| `write` | Mismos cinco campos; coincide con `agents.azure_operations` | Reutilizar la ruta WRITE aislada existente |
| READ/WRITE | Distintos agente, conexión, etiqueta y host | Detectar composición cruzada antes de crear clientes |
| Herramienta READ | `group_list`, argumento `subscription`, aprobación declarada `always` | La configuración no puede ampliar la capability |
| Fuentes antiguas | No mezclar JSON con overrides de catálogo/READ/WRITE | Evitar precedencias ambiguas |
| POC/probes/legacy | Nombres reservados rechazados; READ v1/v2 histórico excluido | No reactivar rutas descartadas |

Los campos adicionales, roles ausentes y claves JSON duplicadas se rechazan.
El catálogo es inmutable. El loader utiliza únicamente el mapping recibido;
no lee `os.environ` como fuente alternativa. El perfil histórico continúa
disponible cuando no se ha activado el JSON; no es fallback de un JSON inválido.

Ejemplo sintético, sin recursos desplegados ni credenciales:

```json
{
  "schema_version": "1.0",
  "project_endpoint": "https://foundry-a.invalid/api/projects/support-a",
  "agents": {
    "classification": {"name": "agent-a-classification", "version": "3"},
    "knowledge": {"name": "agent-a-knowledge", "version": "3"},
    "alert_triage": {"name": "agent-a-alert-triage", "version": "3"},
    "procedure_execution": {"name": "agent-a-procedure-execution", "version": "3"},
    "azure_operations": {"name": "agent-a-azure-operations", "version": "3"},
    "itsm": {"name": "agent-a-itsm", "version": "3"},
    "communication": {"name": "agent-a-communication", "version": "3"},
    "reviewer": {"name": "agent-a-reviewer", "version": "3"}
  },
  "read": {
    "agent_name": "agent-a-rg-list", "agent_version": "1",
    "connection_reference": "mcp-a-read", "server_label": "mcp-a-read",
    "server_url": "https://mcp-a-read.invalid/"
  },
  "write": {
    "agent_name": "agent-a-azure-operations", "agent_version": "3",
    "connection_reference": "mcp-a-write", "server_label": "mcp-a-write",
    "server_url": "https://mcp-a-write.invalid/"
  }
}
```

Este ejemplo documenta el esquema; no se activa en el entorno actual. Los valores
reales se completan desde la publicación de cada destino durante la entrega 4/5.

## Cambios y justificación

- `foundry_deployment.py`: resolver y validar la declaración completa antes de
  crear dependencias de proveedor; reutilizar los contratos READ y WRITE actuales.
- Composición raíz y factories Foundry: propagar catálogo y fingerprint una vez;
  mantener la selección de credenciales productivas existente.
- Workflow y composición Azure: compartir el mismo registro de autoridades READ
  con operaciones y transición, incluidas las factories humana y de continuación.
- Transition executor/gate/aceptación RG List: recibir autoridad de composición;
  conservar validación de identidad, contenido, suscripción, correlación y replay.
- Nodo de clasificación: ID ligado al fingerprint sólo en el perfil nuevo;
  el SDK impide restaurar un checkpoint bajo otra declaración Foundry.
- Dos pruebas antiguas del grafo: sustituir conteo exacto de sentencias AST por
  construcción nativa y comprobación de dependencias. Se conservan sus garantías
  sobre lector, ledger WAIT, ledger de dispatch y aristas del grafo.

## Verificación

Entorno de preparación: CPython 3.14.10 Linux, dependencias runtime fijadas por
el repositorio; pytest 9.2.0 y pytest-asyncio 1.5.0. Sin actualizar los requirements.
Se instaló `socksio` sólo en el entorno de prueba por el proxy local; no es un
cambio de dependencia del producto ni una modificación de la red.

Resultado final NON-LIVE: **3.400 passed, 24 deselected, 3 warnings**, en 56,86 s.
Se añadieron 67 casos a las tres suites nuevas. La ejecución focal inicial fue
105 PASS; el primer conjunto ampliado fue 179 PASS. No se suman esos focales
para calcular la regresión completa.

La primera regresión completa detectó 14 fallos por `socksio` ausente en este
entorno y dos pruebas AST que exigían el número exacto de sentencias del selector.
Se corrigió la dependencia local y se sustituyeron esas dos pruebas por checks
nativos de composición que mantienen sus invariantes. La regresión final pasó
con el conjunto exacto de código, incluidas las pruebas de checkpoints.

Los tres avisos reportados son SessionStore experimental, deprecación de la
política de event loop en una prueba SDK y rechazo previsto de un tipo no
serializable en una prueba de snapshot. pytest-asyncio también emite un aviso
inicial por el scope de fixtures no configurado. No se cambió la configuración
de pytest para ocultarlos. El resultado Windows se registra por separado.

Pruebas añadidas:

- `tests/config/test_foundry_deployment.py`: A/B, configuración inválida antes de
  proveedores, perfiles contradictorios y composición productiva real hasta los nodos.
- `tests/workflows/incident_resolution/test_selected_read_acceptance.py`: resultado
  del servidor seleccionado, servidor ajeno, vacío explícito y negativos de contenido.
- `tests/workflows/incident_resolution/test_deployment_checkpoint_compatibility.py`:
  checkpoints nativos; misma configuración reemite HITL sin llamar agentes;
  cambios de configuración y cruce con legacy se rechazan antes de handlers.

Regresión reproducible en la raíz del repositorio Windows:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest -q
```

`pytest.ini` excluye `live` y `local_container`. No configurar el perfil nuevo ni
arrancar la aplicación para ejecutar esta regresión.

## Reversión y siguiente acción

El paquete es código/configuración sin migración SQL ni despliegue. La rama de
trabajo permite revisar o revertir el cambio sin alterar el baseline de producto.
Un checkpoint del perfil nuevo requiere su configuración y código compatibles;
volver al código anterior no migra esos checkpoints ni borra consumo operacional.

Siguiente acción: aplicar el candidato en la copia Windows limpia, ejecutar la
regresión NON-LIVE, conciliar su resultado y completar la aceptación de la entrega 2.
Después continúa la entrega 3: core neutral y recuperación. Los accesos, datos,
identidades y factoría completa se cualifican en sus entregas previstas.
