# Entrega 3 — núcleo y recuperación: primer paquete

Fecha: 16/11/2026. Proyecto Creación de agentes.
Base publicada: `6d141382a84e22c97e4c461eb869c96d8433ac2e`, árbol
`3e8e9f4e6504be406172aa13690d5f0cef995e68`.
La entrega 2 cuenta con 3.400 PASS en Windows, 24 excluidas, 3 avisos,
y comprobación de los 19 blobs publicados. `phase16-wip` conserva `a88c79c5`.

Actualización posterior: este primer paquete se validó en Windows con **3.428
passed, 24 deselected, 3 warnings**, 99,82 s, exit code 0, y se publicó en
`897807a972275e532877aa6b4354e8609f80f264`, rama `codex/e3-core-recuperacion`.
Se comprobaron sus 19 blobs remotos. Informe `E3_R1_WINDOWS_20261116_165301.xml`,
SHA256 `0747d3a550a4adcf621fea5de8d100d809616b38c5b703f60e5786adf1eb255a`.
Las menciones a Windows pendiente describen la preparación de ese primer paquete;
quedan superadas por esta evidencia. Los apartados siguientes conservan su alcance
histórico. La entrega 3 continúa con el
[segundo paquete: contrato de continuación](e3-continuation-boundary.md).

## Resultado y alcance

La composición del workflow de incidente sale de `channels/teams/bootstrap.py`
hacia `workflows/incident_resolution/composition.py`. Teams compone su transporte,
autorización de operador y presentación; solicita al núcleo una factoría que
también puede usarse sin importar Teams. La misma factoría se entrega al handler
y al worker. Cada llamada crea un grafo, conserva las instancias de agentes y
los registros de consumo, y mantiene las autoridades READ/WRITE seleccionadas.

El codec de checkpoints sale del adaptador Azure SQL hacia
`persistence/checkpoint_codec.py`. Conserva los bytes JSON del formato existente
`WorkflowCheckpoint.version == "1.0"`; no introduce envoltorio ni migración SQL.
La versión de formato no es la versión del SDK. Rechaza versión desconocida,
JSON ambiguo por claves duplicadas y tipos no permitidos. Antes de guardar,
comprueba que el mismo codec puede restaurar el estado; si no, no abre SQL.

Se corrige además una sustitución implícita: un agente o ledger inyectado cuyo
valor booleano sea falso se conserva. Sólo `None` activa el default histórico
del constructor directo. La factoría compuesta exige stores explícitos; eso no
certifica por sí solo que su implementación sea durable.

Este paquete no termina la entrega 3. El protocolo de continuación todavía
contiene tipos Teams, y la aplicación productiva sigue arrancando el host Teams.
No se afirma que todo el runtime sea independiente del canal, que una sesión
remota se restaure tras un reinicio ni que se haya ensayado concurrencia SQL real.

## IDs y criterio de salida de este paquete

| ID conservado | Contribución | Estado del alcance |
| --- | --- | --- |
| F30-T01 / F31-T01 | Mapa de contratos, SQL y consumidores descritos abajo | Revisión de los componentes citados; no inventario semántico de todo el repositorio |
| F30-T02 | Matriz de ventanas de recuperación y límites | Contrato de continuidad explícito; escenarios pendientes separados |
| F30-T03 | Factoría independiente del canal y codec encapsulado | Implementado en candidato |
| F30-T04 / F40-T03/T04 | Compatibilidad histórica, autoridad compartida, negativos y regresión | Evidencia NON-LIVE; Windows pendiente para este paquete |
| F31-T02/T03/T04 | Tablas, transacciones, leases y carreras | Sin modificación de esquema; pruebas SQL reales pendientes |
| F32/F37/F38/F39 | Notificación, incertidumbre y atestación | Carencias identificadas; no cierres globales |

Salida local: grafo construible sin Teams, autoridades conservadas, checkpoint
anterior restaurado sin invocar agentes, estado no restaurable rechazado antes
de SQL y regresión satisfactoria. La aceptación Windows y la publicación se
registran por separado.

## Mapa de estado y consumidores revisados

| Estado | Implementación / consumidor | Autoridad y límites observados |
| --- | --- | --- |
| Checkpoint | `azure_sql/checkpoint_storage.py`; `runtime/procedure/approval_resumer.py`; workflow MAF | Tabla `workflow_checkpoints`, clave checkpoint_id, actualización bloqueada e inserción; firma de grafo al restaurar. No reinicia consumo |
| Aprobación | `azure_sql/pending_approval_store.py`; `teams/incident_approval_processor.py` | `pending -> claimed -> completed`; claim condicional, decisión y correlación persistidas; no vuelve a pending |
| Dispatch | `azure_sql/operation_dispatch_ledger.py`; `executors/azure_operations.py` | INSERT por operation_id único antes de la invocación; se conserva aunque el resultado sea incierto |
| WAIT | `azure_sql/wait_recheck_consumption_ledger.py`; transición/observación | ABSENT -> IN_PROGRESS -> COMPLETED; reanudación de observación READ, sin rehabilitar WRITE; no identifica propietario exclusivo de una observación en progreso |
| Continuación | `azure_sql/incident_continuation_store.py`; `teams/incident_continuation_worker.py` | Claim atómico con UPDLOCK/READPAST/READCOMMITTEDLOCK; recuperación preaprobación vuelve a comprobar pending+NULL bajo lock |
| Sesión cognitiva | `azure_sql/session_store.py`; `runtime/agent_session_snapshot.py`; `runtime/conversation_session_lifecycle.py` | Snapshot de AgentSession bajo clave de conversación; no es el checkpoint ni la autorización; get/run/set no equivale a una lease distribuida de turno |
| Invocación MCP | `agents/foundry_agents.py` | AzureOperationsInvocation conserva agente, sesión, respuesta y owner_token en memoria; continuación exige la misma instancia |
| Conversación Teams | `azure_sql/conversation_binding_store.py`; bootstrap y adaptador outbound | Dirección de transporte por tenant/conversation; no concede permiso operacional |
| Outbox y atestación | `attestation/governor_outbox.py`, `attestation/worker_entrypoint.py`, `azure_sql/attestation_journal.py` | Outbox insert-only, claves/digest, journal separado con reserva transaccional; commit incierto no otorga propiedad ni autoriza retry |

Se revisaron las migraciones 001–005 y los contratos anteriores en los puntos
de composición, serialización, claim, recovery y consumo. Son código/IaC del
repositorio: no prueban el esquema o los permisos actualmente desplegados.
Las pruebas de adapters sustituyen la conexión SQL; los tests SQLite prueban
otro motor. Ninguno certifica locks ni aislamiento efectivo de Azure SQL.

## Ventanas de recuperación

| Ventana | Comportamiento permitido / existente | Lo que falta cualificar |
| --- | --- | --- |
| Antes de reclamar la continuación | Trabajo pending puede ser reclamado por el store | Dos workers reales SQL y fallos de conexión |
| Continuación claimed, aprobación pending+NULL | Recovery con guard SQL y presupuesto de tres intentos del worker | Caída dura: el catch no se ejecuta; no hay barrido general ni lease con vencimiento acreditada |
| Aprobación claimed/completed | El worker falla cerrado y no reencola para ejecutar de nuevo | Conciliación del resultado y recuperación independiente de comunicación |
| Pausa MCP dentro del proceso | Se conserva la misma instancia y sesión con owner_token | Reinicio del proceso y reconstrucción de la continuación remota, no implementados aquí |
| Dispatch consumido, respuesta ausente | Conservar consumo, observar/conciliar o escalar | Evidencia externa que distinga efecto ocurrido de efecto no ocurrido |
| WAIT IN_PROGRESS | Puede reanudar una observación READ con el mismo identificador | Exclusión entre observadores concurrentes y publicación de resultado en SQL real |
| Outbox/journal: commit incierto | STOP sin convertir un readback posterior en nueva autoridad | Recuperación y prueba del job instalado con su identidad separada |
| Resultado operativo completo, notificación fallida | No repetir la operación | Persistir/reintentar sólo la notificación con idempotencia; hoy se envía antes de completar el job |
| Cambio de configuración Foundry | Firma del grafo F46 rechaza checkpoint incompatible | Afinidad general con release/esquema, drenaje y migración explícita |

El entrypoint del atestador procesa una clave `--operation-sha256` por ejecución.
Eso acredita una interfaz finita, pero no demuestra por sí solo la selección
automática de lotes pendientes por varios workers. La reserva en journal y la
selección de trabajo son responsabilidades distintas. Se mantiene como pendiente
de esta entrega el diseño/ensayo de lotes, respetando la autoridad insert-only.
No se añaden permisos para que core/MCP arranquen o modifiquen el job.

## Decisiones y justificación de cambios

1. Extraer opciones y factoría a la ubicación del workflow: el canal deja de
   construir bindings WRITE y de expandir configuración de procedimientos.
   Se reutilizan PendingApprovalStore, CheckpointStorage, los dos ledgers y el
   reader existentes; no se inventan interfaces ITSM sin consumidor real.
2. Validar opciones antes de dependencias de proveedor: conservar el rechazo
   temprano y los negativos de selección de la entrega 2.
3. Mantener agentes, stores y binding reader por identidad: no perder afinidad
   de sesión ni seleccionar memoria local en lugar de un ledger suministrado.
4. Encapsular el codec privado: dejar una frontera explícita para futuros cambios
   del SDK y conservar el formato histórico. La comprobación previa a escritura
   evita guardar un checkpoint que este lector rechazaría después del reinicio.
5. Mantener allowlist exacta y almacenamiento de confianza: la serialización MAF
   usa pickle para ciertos objetos; un JSON válido no convierte datos externos en
   checkpoints aceptables. No se añaden tipos por prefijo ni registro global.
6. Mover los spies de tests a la frontera extraída y sustituir un check AST por
   composición ejecutada: el requisito es transmitir el ledger, no mantener una
   función anidada dentro de Teams. No se suprimen casos de prueba.

## Evidencia y compatibilidad

El fixture `tests/fixtures/checkpoints/incident_v1_before_e3.json` se generó con
el código publicado anterior a este cambio, MAF 1.13.0 y agentes sintéticos,
deteniéndose en la primera aprobación HITL. No contiene una sesión LIVE.
El codec nuevo lo lee y la factoría nueva reemite el mismo request_id sin
ejecutar agentes ni producir salida terminal.

También se verifica la identidad de agentes, ledgers, binding READ y almacenes
del lector WRITE; ausencia de importación de Teams al construir el núcleo;
rechazo de versión desconocida antes de reconstruir objetos; tipos excluidos
antes de abrir SQL y compatibilidad byte a byte del escritor JSON existente.

Pruebas focales: **171 passed, 1 warning**. De ellas, 28 casos son nuevos.
Regresión completa Linux: **3.428 passed, 24 deselected, 3 warnings**, 63,62 s,
exit code 0. Son los 3.400 casos anteriores más 28 nuevos, sin sumar focales.
Después se explicitó UTF-8 al leer el fixture en dos pruebas para portabilidad
Windows; se volvieron a ejecutar las dos suites nuevas. No cambió código de
producto después de la regresión completa. Windows permanece pendiente.
Las primeras ejecuciones focales localizaron dos comprobaciones ligadas a la
ubicación antigua y la sustitución de un ledger de valor booleano falso. Se
adaptaron las primeras a la nueva frontera y se corrigió la sustitución; el
resultado focal citado corresponde al código final de esos cambios.

SDK/runtime sin actualización: Python 3.14.10; agent-framework-core 1.13.0;
agent-framework-foundry 1.10.4. No hay DDL, llamadas Foundry/MCP, migraciones,
cambios de identidad ni despliegues Azure en este paquete.

## Fuentes y límites

- [Microsoft: checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints),
  consultado el 16/11/2026: CheckpointStorage, serialización, allowlist y
  responsabilidad de proteger el almacenamiento.
- Código instalado y fijado de `agent_framework`: `_workflows/_checkpoint.py`
  (`WorkflowCheckpoint.version`, `from_dict`) y `_checkpoint_encoding.py`
  (encoder/decoder restringido). El comportamiento del candidato se valida con
  esas versiones; no se sustituye por ejemplos de otra versión de la documentación.
- Plan canónico `PLAN_EJECUCION_MVP_REFACTORIZACION_20261116.txt`, sección 6:
  misma entrega 3 y mismos IDs; no se añaden fases ni gates.

## Continuación y reversión

Después de aceptar este paquete en Windows, continúa la extracción del contrato
de continuación ligado a Teams y el diseño de recuperación de jobs huérfanos,
notificaciones y turnos de sesión. Los cambios transaccionales se aplicarán sólo
contra una carencia y con ensayo SQL; no mediante un reset de consumos.

Reversión de este paquete: restaurar su código compatible. Los checkpoints
válidos mantienen el formato anterior y no se modifican tablas. Un formato
desconocido o un tipo rechazado exige investigación, nunca desactivar controles.
No borrar aprobaciones, dispatch, WAIT, outbox ni journal para facilitar rollback.
