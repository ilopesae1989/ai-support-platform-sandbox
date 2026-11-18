# Entrega 3, P8-P2 R1 — admisión durable y cola por afinidad

Fecha: 17/11/2026. Proyecto Creación de agentes.
Base publicada: `a81f5111dbaa9615059b75aed1c71f5f30378707`.
Árbol base: `797388284b25a4bbad2f848a11c4a165a4fec821`.
P8-R1 publicado y verificado, con 3.780 PASS en Windows y Linux.

## Alcance y decisión

Segundo paquete del punto 8 de entrega 3: registra la ejecución antes del primer
agente, conserva esa identidad al llegar a HITL y selecciona trabajo compatible
antes de incrementar intentos. Incluye el mismo filtro en la recuperación.
Es una composición candidata explícita. **No activa el host productivo, no termina
P8 ni acredita una actualización entre releases desplegadas.**

La revisión encontró que `ProcedureRequestExecutor` generaba `workflow_id` después
de clasificación/conocimiento/triage. `pending_approvals` ya relaciona ese ID con
aprobación, request y checkpoint. Se reutiliza la identidad existente: no se crea
otra identidad independiente para el incidente ni una segunda tabla de correlaciones
HITL. En la ruta nueva se genera antes, se registra y se conserva en el estado.

La cola candidata usa `incident_affine_continuation_jobs`, separada de
`incident_continuation_jobs`. El lector histórico no conoce afinidad y no puede
filtrar sus filas. Separar ambas evita que reclame una fila candidata; además
permite conservar la ruta histórica sin exigir inmediatamente un esquema nuevo.
Las diferentes afinidades candidatas comparten su tabla y se filtran por huella.
Esto tiene un coste: el drenaje deberá inventariar las dos colas y la admisión.
No se permite copiar filas, rellenar históricos ni ejecutar simultáneamente
hosts de releases distintas como si ya existiera routing productivo cualificado.

## Orden del paquete y justificación

| Paso | Implementación | Motivo |
| --- | --- | --- |
| 1. Admisión | `IncidentExecution`, puerto y adaptadores de persistencia | Guardar una asignación inmutable antes de agentes y del checkpoint de entrada |
| 2. Correlación | Input admitido, clasificación y routing | Usar el mismo ID como `workflow_id`, sin extraer autoridad del canal o del LLM |
| 3. Handoff | Resolver `pending_approvals` y fijar `execution_id` en la cola candidata | Vincular la decisión autorizada a la ejecución ya admitida |
| 4. Claim | Filtro por afinidad antes del límite/UPDATE, dentro de una transacción | El consumidor incompatible no toma propiedad ni consume intentos |
| 5. HITL y recuperación | Propietario, generación, instante, ejecución y consumo comprobados bajo bloqueos | Conservar las garantías P4–P7 y no recuperar trabajo ajeno o consumido |
| 6. Composición | Fábrica y worker ligados al mismo almacén; prevalidación del grafo | Un cambio local de configuración falla antes del claim |
| 7. Validación | SQLite real, MAF nativo, contratos SQL con dobles y regresión NON-LIVE | Separar evidencia ejecutada de cualificación pendiente en SQL real |

## Admisión e identidad

`admit_incident_workflow_input` es una API del host de confianza. Genera un
`wf-<UUID>` mediante la función existente, calcula la huella del input normalizado
y confirma la asignación antes de devolver el input que se entrega a `workflow.run`.
La huella cubre alerta completa y correlación de conversación; no incluye el ID
del registro. La afinidad se obtiene del almacén configurado, no de la alerta.

`incident_executions` conserva `execution_id`, `input_sha256`, `affinity_sha256`
y el documento de afinidad completo. Repetir exactamente una asignación es
idempotente; cambiar input, instalación, release o configuración no la sobrescribe.
La lectura valida el documento, su huella y su correspondencia con el almacén.
JSON duplicado, versiones desconocidas y datos corruptos fallan cerrados.

La clasificación exige un input admitido, resuelve el registro y comprueba su
huella antes de llamar a un agente. Guarda `incident_execution_id` en el estado;
routing lo reutiliza como `workflow_id` de la ejecución de procedimiento.
Las aprobaciones existentes propagan así la identidad sin cambiar su payload.
Un input crudo, un registro ausente o un input modificado se rechazan en esa ruta.

La firma inicial del grafo añade `-admitted-v1`: un checkpoint de P8-R1 sin
admisión no se adopta automáticamente. El codec conserva su formato 1.0. La ruta
candidata usa `admitted_incident_checkpoint_allowed_types`, que añade únicamente
`AdmittedIncidentWorkflowInput` a la allowlist; los lectores históricos conservan
sus 55 tipos y no aceptan ese nuevo input. El input histórico sigue
teniendo únicamente alerta y conversación. Las composiciones históricas conservan
su comportamiento e IDs, salvo la corrección de hints SQL descrita abajo.

Esta admisión **no es deduplicación de alertas, una lease de ejecución inicial ni
un protocolo de reintento del arranque**. Cada llamada nueva crea una ejecución,
igual que antes. Si hay un resultado incierto al confirmar admisión, no se debe
crear otra por inferencia. El inventario de admisiones sin arranque/completado y
la recuperación inicial pertenecen al trabajo de admisión/drenaje pendiente.

## Persistencia y transacciones

La implementación común contiene las invariantes; los adaptadores concretos
aportan conexión y esquema. No incorpora ORM, LangChain, nuevos SDK ni A2A.
Los nombres de tablas son internos; los valores se pasan como parámetros.

SQLite exige que aprobación, registro y cola candidata estén en el mismo archivo.
Usa `BEGIN IMMEDIATE`, claves foráneas y cierre explícito de conexión/cursor.
No se promete atomicidad entre archivos. La ruta antigua sigue admitiendo sus
pares de almacenes históricos sin convertirlos a la nueva composición.

Azure SQL exige la misma fábrica de conexiones que el almacén de aprobaciones
y `autocommit=False`. El registro toma bloqueo de fila/rango antes de insertar.
El selector toma `UPDLOCK, READPAST, READCOMMITTEDLOCK` y filtra por afinidad antes
de seleccionar la primera fila. Después valida la asignación y el payload en
la misma transacción, actualiza y confirma. Los errores no se reintentan aquí.
Las lecturas posteriores a un UPDATE se hacen **antes del commit**, bajo sus
bloqueos, para validar la transición; no hay readback tras un commit incierto.

El orden del duplicado de handoff y del consumo HITL empieza por la fila de cola.
Se conservan propietario, intento original, ejecución e instante en el UPDATE.
El claim HITL comprueba la decisión durable y la correlación completa antes de
consumir `pending/NULL`. Consumido HITL, la recuperación no lo vuelve a abrir.
Se conserva el máximo de tres intentos, sin reset por cambio de release.

El recuperador P6/P7 puede recibir el nuevo adaptador mediante su puerto existente.
La selección filtra afinidad antes del límite y cursor; el UPDATE vuelve a
comprobar ámbito, generación e instante. Una candidatura obtenida de otra
instalación no concede permiso para recuperarla.

La fábrica candidata debe usar exactamente el almacén de ejecución que usa su
worker y el almacén de aprobación asociado. Construye y valida el grafo antes
del claim. Eso detecta configuración Foundry modificada sin gastar un intento.
La composición productiva sigue rechazando las variables de activación incompleta.
El launcher y el routing productivos de canales siguen pendientes; una dependencia
mal cableada al handler histórico no se convierte en un dispatcher por afinidad.

## Esquema y compatibilidad de despliegue

`platform/azure-sql/candidates/e3_execution_affinity_v1.sql` es un **candidato**.
No se añade a la secuencia automática de migraciones ni se ejecuta en este paquete.
Crea únicamente el registro y la cola candidata con sus claves e índices. Requiere
el esquema 001; no altera ni rellena tablas anteriores y no concede permisos.
Lectores históricos siguen usando sus tablas. El adaptador candidato requiere
instalar y cualificar el esquema antes de su activación, además de los otros gates.
No interpreta ausencia de esquema como permiso para usar la cola antigua.

## Corrección SQL encontrada durante la revisión

El selector anterior combinaba `READCOMMITTEDLOCK` y `ROWLOCK`. Microsoft los
incluye en el mismo grupo de granularidad y prohíbe más de uno por tabla.
Se conserva `READCOMMITTEDLOCK` para el patrón de cola con READPAST/RCSI y se
retira ROWLOCK del selector anterior y del nuevo. Los tests históricos se
actualizan para rechazar la combinación; se conservan sus IDs.

No se promete ausencia de bloqueos: READPAST no omite bloqueos de página y las
claves foráneas/índices pueden bloquear. El aislamiento de sesión, los planes y
las carreras deben cualificarse con Azure SQL real antes de desplegar.

## Evidencia y límites

Los informes focales y FULL, conteos, hashes y comparación de IDs se entregan
en el expediente del paquete. La aplicación y validación Windows y la publicación
de este incremento permanecen pendientes hasta recibir sus resultados.

Las pruebas nuevas cubren: seis variaciones de afinidad sin modificar cola/HITL;
persistencia al reabrir; input y registro corruptos; histórico sin admisión;
colas aisladas; duplicados; competencia por un claim; generaciones antiguas;
recuperación filtrada y presupuesto; pérdida del acuse del commit; recorrido nativo
hasta rechazo HITL y finalización con checkpoints en disco; reapertura del input
admitido y rechazo de su codec histórico; configuración modificada antes del claim; y
consultas/rollback/cierre de conexiones SQL con dobles.

No se usa una operación Azure real ni falsa para acreditar esta frontera: la prueba
integrada termina por rechazo humano. SQL con dobles no demuestra que la consulta
se haya ejecutado en un servidor ni cualifica su concurrencia o rendimiento.

P8-P2 R1 obtuvo posteriormente 3.852 PASS en Windows y se publicó en `c14c077`.
El [inventario P8-P3](e3-execution-inventory.md) desarrolla la observación de
ambas colas y las admisiones sin arranque confirmado.

## Pendientes registrados al preparar P8-P2

- Admisión y drenaje coordinados, inventario completo, fin de ejecuciones y carrera
  del último conteo; admisiones cuyo arranque no quedó confirmado.
- Diagnóstico durable de incompatibilidad. El selector incompatible devuelve idle
  y preserva filas; no constituye por sí solo una alarma operacional.
- Wiring del host/canales y política de instalación; sesiones remotas y notificación
  durable; reconciliación de efectos inciertos posteriores al consumo HITL.
- Cualificación Azure SQL, esquema/permisos, despliegue N a N+1, rollback y drenaje
  de históricos con su artefacto original acreditado.

MVP conserva drenaje ordenado: N termina WAIT/HITL/trabajo pendiente antes de N+1;
timeout detiene actualización. No se retira el bloqueo productivo. F27 LIVE sigue
pausada; entrega 3/F30/F31/F37 abiertas; entregas 4–8 y F27–F48 conservan sus IDs.

## Referencias

- [Identidad y afinidad P8-R1](e3-release-affinity-contract.md).
- [Propiedad del intento](e3-continuation-ownership.md), [claim coordinado](e3-continuation-hitl-claim.md)
  y [recuperación](e3-continuation-recovery.md).
- [Microsoft: table hints](https://learn.microsoft.com/en-us/sql/t-sql/queries/hints-transact-sql-table),
  apartados READPAST y grupos de hints, consultados el 17/11/2026.
- [Roadmap](roadmap-f27-f48.md). Las decisiones AI-103/AI-500/AB-100 y la retirada
  del diseñador Foundry no se redefinen en este incremento.
