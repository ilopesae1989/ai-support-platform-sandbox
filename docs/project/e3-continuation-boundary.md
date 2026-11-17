# Entrega 3 — contrato de continuación independiente del canal

Segundo paquete, 16/11/2026. Proyecto Creación de agentes.
Base publicada: `897807a972275e532877aa6b4354e8609f80f264`, árbol
`cb4fcf6f65773e1b664624472ad7d27c39e26c91`. Se comprobaron los 19 blobs
del primer paquete, su avance de un commit sobre F46 y la evidencia Windows:
3.428 PASS, 24 excluidas y 3 avisos. El primer paquete está publicado; esta
segunda extracción permanece candidata hasta aceptación Windows y publicación.

Actualización posterior: este segundo paquete se publicó en
`5a81ea8cbd37de0646691405a60c58fc32b2e8fd`, rama `codex/e3-core-recuperacion`,
tras **3.454 passed, 24 deselected, 3 warnings** en Windows, 105,96 s, exit code 0.
Se verificaron los 24 blobs publicados. Informe
`E3_P2_R1_WINDOWS_20261116_172911.xml`, SHA256
`0574ecabd89bb00f2f8483a4fdbe473157af407398598c6127bc3925202bee66`.
Esta evidencia supera las menciones históricas a candidato/Windows pendiente.
Continúa [el tercer paquete: procesamiento HITL y evidencia](e3-hitl-processing.md).

## Problema y resultado

El adaptador Azure SQL importaba `AuthorizedTeamsApprovalInvocation` y el modelo
de trabajo desde `channels/teams`. El worker, el contrato de persistencia y la
implementación SQLite también residían en ese canal. Por ello otro host no podía
reutilizar la continuación sin importar Teams.

El contrato y el worker pasan a `runtime`; SQLite pasa a `persistence/sqlite`.
Los almacenes reciben explícitamente el codec del tipo de invocación autorizado
que selecciona su host. El host Teams proporciona `TEAMS_CONTINUATION_CODEC`;
el payload no selecciona clases ni importa módulos. Se mantiene la identidad
Teams completa y su autorización actual. El worker recibe el procesador y el
notificador existentes por inyección, conservando su orden de ejecución.

Un proceso nuevo puede abrir trabajos persistidos y usar el mismo worker con
un modelo sintético de otro adaptador, bloqueando todas las importaciones de
`src.channels` y `microsoft_teams`. Esto demuestra independencia de esa frontera
y restauración local de la cola; no certifica recuperación remota Foundry/MCP.

## Decisiones, archivos y motivo

| Cambio | Motivo y límite |
| --- | --- |
| `runtime/procedure/authorized_approval.py` | Base común con policy_id y ApprovalChannelAction. Heredar o instanciar el modelo no acredita autenticación ni autorización |
| `runtime/incident_continuation_store.py` | Puerto, errores, estados y job genérico fuera de Teams; cada lector usa el modelo concreto para conservar los campos de identidad |
| `runtime/incident_continuation_codec.py` | Encoder/decoder con tipo explícito elegido por composición; misma representación JSON canónica, sin descubrimiento dinámico ni nuevo envelope |
| `runtime/incident_continuation_worker.py` | Reutilizar el ciclo de claim, proceso, notificación y recuperación; no introducir otro worker con reglas distintas |
| `persistence/sqlite/incident_continuation_store.py` | Separar almacenamiento local del transporte. Se conservan conexiones, SQL y transiciones; no sustituye Azure SQL productivo |
| `persistence/azure_sql/incident_continuation_store.py` | Eliminar importaciones del canal e inyectar codec obligatorio; no cambiar consultas, locks, commit ni rollback |
| `channels/teams/continuation_payload.py` y composición | Seleccionar el esquema histórico Teams desde el host confiable; mantener el canal y el procesador actuales |
| Fachadas en `channels/teams/incident_continuation_*` | Conservar importaciones públicas y constructor local existentes; no duplicar reglas del worker ni de SQLite |
| Pruebas de composición y cierre de conexiones | Seguir comprobando los argumentos reales del adaptador y las conexiones en su nueva ubicación; no retirar cobertura |

La firma interna de `AzureSqlIncidentContinuationStore` requiere ahora
`payload_codec=`. El único consumidor productivo encontrado en el repositorio,
`build_azure_sql_teams_hitl_persistence`, lo aporta explícitamente. Los consumidores
de prueba también se actualizan. El constructor SQLite de la fachada Teams
conserva su firma. Un consumidor externo del constructor SQL tendrá que pasar el
codec del modelo autorizado correspondiente; no hay default que importe Teams.

## Autoridad y compatibilidad

- La autenticación de actividad, comprobación de tenant, correlación de identidad
  y pertenencia al grupo Teams siguen en el adaptador original. La herencia del
  modelo común no permite saltarse esas comprobaciones.
- La invocación persistida sigue siendo una decisión humana previamente
  autorizada. Ni el modelo base, ni JSON, ni un codec conceden permisos Azure.
- Se conservan approval_id, decisión, política e identidad. Un duplicado exacto
  sigue siendo idempotente; cambiar identidad, política o decisión entra en
  conflicto. Una correlación de fila y payload distinta sigue siendo rechazada.
- El formato Teams histórico no cambia: se lee un fixture escrito con el código
  publicado anterior y se comprueba igualdad byte a byte al volver a codificar.
  No hay DDL nuevo ni migración de los trabajos pendientes.
- Enqueue exige una instancia del tipo seleccionado por el host. Diccionarios
  crudos u otro modelo de canal se rechazan antes de abrir SQL.
- La ruta productiva conserva los procesadores y las evidencias Teams. El
  adaptador alternativo de las pruebas es sintético, no una nueva entrada pública.
- No se mezclan varios formatos de canal dentro de una misma cola sin un contrato
  de selección/migración posterior. Este paquete inyecta un codec por almacén.

## Recuperación preservada y límites

El cuerpo ejecutable de `process_next_once` y `run` es idéntico al anterior
según comparación AST. Se conservan las ocho constantes SQL y las trece
sentencias literales ejecutadas por el adaptador SQLite.

El worker sólo recupera automáticamente una continuación claimed si la
aprobación sigue pending y sin decisión, dentro del presupuesto actual de tres
intentos. Azure SQL conserva la comprobación transaccional de la aprobación y
el propietario exacto. Una aprobación consumida, una lectura fallida del estado
o el agotamiento del presupuesto conservan el comportamiento fail-closed.

Se mantiene el envío de notificación antes de completar el trabajo. Este paquete
no añade una outbox de notificación ni resuelve la ventana entre envío y acuse.
Tampoco añade leases, barrido de huérfanos, recuperación de una sesión MCP perdida
o afinidad con versiones de release. Son pendientes de la misma entrega 3.

La prueba de reinicio usa SQLite y un procesador sintético que consume la
aprobación; no invoca Foundry ni herramientas operacionales. Las pruebas del
adaptador Azure SQL usan conexiones sustituidas. No prueban aislamiento,
concurrencia o permisos del SQL desplegado. La recuperación SQLite conserva la
lectura separada del approval store; no se presenta como transacción distribuida.

## Pruebas y criterio de salida

Pruebas focales: **504 passed, 1 warning**. Incluyen 26 casos nuevos:

- formato histórico y cuatro estados de la fila SQL;
- reapertura SQLite e idempotencia de un payload anterior;
- conflictos de identidad, política y decisión con otro modelo de adaptador;
- rechazo de tipos/codec incorrectos, identidad incompleta, autoridad añadida
  y correlación de aprobación sustituida;
- proceso nuevo que completa una continuación persistida sin importar canales,
  conserva consumo y devuelve IDLE ante el intento posterior.

Regresión completa Linux: **3.454 passed, 24 deselected, 3 warnings**, 64,19 s,
exit code 0. Conserva los 3.428 casos anteriores y añade los 26 indicados.
Se usaron las mismas dependencias del paquete anterior; no se actualizaron SDKs.
Windows: pendiente para este segundo paquete. La aceptación del primero no
sustituye esta validación. Los resultados focales no se suman a la regresión.

IDs conservados: F30-T01/T03/T04, F31-T01 y apoyo F40. Salida del paquete:
worker/puerto reutilizables sin Teams, payload histórico compatible, autoridad
y transiciones conservadas, pruebas NON-LIVE satisfactorias. No cierra las fases
F30/F31 ni la entrega 3 completa.

## Siguiente trabajo y reversión

Continúa la separación del procesador HITL y la generación de evidencia todavía
ubicados en Teams, utilizando los consumidores existentes. Después se abordan
las ventanas de recuperación ya identificadas con cambios y pruebas acotados;
no se añade una fase nueva al plan canónico.

La reversión de código conserva el mismo formato Teams y las mismas tablas.
No borrar trabajos, aprobaciones, dispatch, WAIT, outbox o journal para facilitarla.
Un futuro canal/formato necesitará su propio contrato antes de escribir datos
que una versión anterior no pueda interpretar.
