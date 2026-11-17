# Entrega 3, P6 R1 — recuperación pre-HITL por lotes explícitos

Fecha: 17/11/2026. Proyecto Creación de agentes.
Base publicada y verificada: `148ff9dcb4e73f23ea66059c75c6c1b26ef470fb`.
Árbol base: `d0f2a9b9814c82415ceb8d0a0ad83be29d02a90f`.
P5 R2: 3.562 PASS en Windows y Linux; publicación completada.

## Problema y decisión

P5 impide que un intento sustituido consuma la aprobación HITL. Sin embargo,
si el proceso muere después del commit de `claim_next`, no ejecuta el catch del
worker. La continuación permanece claimed aunque la aprobación siga pending.
P6 añade una selección limitada y una operación transaccional de recuperación
que puede invocar un consumidor de confianza. No instala un temporizador,
endpoint, servicio ni activación automática en el host.

La antigüedad **selecciona candidatos; no demuestra que un proceso haya muerto**.
Un trabajador pausado puede reaparecer. La protección consiste en volver a
comprobar propietario, intento, fecha y aprobación dentro de la transacción,
y en que el consumo HITL posterior de todos los workers pase por el contrato P5.
Tras reencolar, el intento antiguo pierde autoridad aun si el identificador de
worker se reutiliza. El siguiente claim incrementa el contador; no se reinicia.

## Contrato y fases de este incremento

1. Revisar la base publicada, los tiempos de la cola y la frontera de claim P5.
   Evita construir el recuperador sobre una lectura de pending fuera de la
   transacción o sobre supuestos de lease inexistentes.
2. Añadir el puerto opcional `IncidentContinuationRecoveryStore` y el servicio
   `IncidentContinuationRecovery.run_batch`. Permite reutilizar el mismo core
   sin depender de Teams o del proveedor de persistencia.
3. Implementar selección y recuperación en los adaptadores SQLite y Azure SQL.
   Conserva tablas, payloads, versión de SDK y configuración por cliente.
4. Probar caída abrupta, sustitución del intento, carreras, presupuesto, paginación
   y errores de commit; ejecutar la regresión NON-LIVE.
5. Validar en Windows el árbol exacto del parche y aceptar su informe antes de
   publicar. La activación del barrido y la aceptación SQL real son pendientes
   posteriores, sin cerrar la entrega 3 ni F30/F31.

### Selección y resultado

- `stale_before`: fecha Unix finita y no negativa, obligatoria; comparación `<`
  estricta contra `updated_at`. El llamador mantiene la misma fecha de corte al
  paginar un ciclo. No existe un TTL predeterminado ni se recibe del canal.
- `limit`: entero exacto de 1 a 100. Acota el número de candidatos y de intentos
  de transición por llamada; no acota el tiempo de espera SQL ni garantiza un
  coste constante del plan de consulta.
- `after_id`: cursor exclusivo opcional por approval_id, con orden del motor.
  Evita que aprobaciones consumidas o presupuestos agotados bloqueen siempre
  los siguientes candidatos. No es una instantánea de toda la cola. Un nuevo
  ciclo vuelve a empezar sin cursor para revisar filas aparecidas anteriormente.
- Se leen sólo approval_id, propietario, intento y updated_at; no se deserializa
  la invocación. Las filas terminales/pending quedan fuera de la selección.
- Se valida la página completa antes de modificar filas. Cada resultado conserva
  el candidato original y uno de `requeued`, `rejected` o `uncertain`.
- `requeued` significa que se recibió confirmación del commit de esa transición;
  otro worker puede reclamarla inmediatamente. No significa estado pending
  estable, aprobación consumida ni ejecución del procedimiento.
- `rejected` conserva la fila ante cambio de estado/propiedad/fecha, presupuesto
  agotado o aprobación ausente, consumida o inconsistente. No se adopta el
  intento actual ni se marca el trabajo como failed por haber envejecido.
- Cualquier otro error detiene el lote con `halted=True`, sin reintento, relectura
  como permiso ni cursor de continuación. Se conservan resultados previos y
  sólo el tipo de excepción; no mensajes con datos del proveedor. Una excepción
  en la selección se propaga sin iniciar transiciones.

El consumidor es código de confianza de la misma instalación. Empareja los
stores de ese cliente y conserva/observa los resultados. Este contrato no añade
aislamiento de tenants a una tabla compartida ni autentica operadores externos.

## Persistencia y justificación por archivo

| Archivo | Cambio y razón |
| --- | --- |
| `src/runtime/incident_continuation_recovery.py` | Candidatos inmutables, puerto opcional y lote finito. Aísla la política de recuperación del canal y evita imponerla al loop existente del worker |
| `src/persistence/sqlite/incident_continuation_store.py` | Selección sobre fichero existente y recuperación en `BEGIN IMMEDIATE`, usando la conexión coordinada de P5. Evita abrir una ventana entre aprobación y actualización |
| `src/persistence/azure_sql/incident_continuation_store.py` | Selección TOP parametrizada y transición con fábrica compartida, autocommit explícitamente False y guardas transaccionales. Conserva el orden aprobación → cola del claim P5 |
| `tests/runtime/test_incident_continuation_recovery.py` | SQLite real, proceso con salida abrupta y callbacks sintéticos. Comprueba persistencia, carreras, bloqueo del intento antiguo y tratamiento de incertidumbre |
| `tests/persistence/azure_sql/test_continuation_recovery.py` | Dobles SQL que comprueban parámetros, guardas, orden, OUTPUT, rollback y cierre. No acreditan el comportamiento del servidor |
| Este documento, `e3-continuation-hitl-claim.md` y `roadmap-f27-f48.md` | Registra alcance P6, publicación P5 y siguiente aceptación, conservando IDs y pendientes del plan |

En SQLite se reutiliza la transacción que abre cola/aprobación existentes con
`mode=rw`, adjuntando la segunda base cuando corresponde. La recuperación sólo
escribe en la cola. No se afirma atomicidad de cambios simultáneos en dos
ficheros WAL. No cambia journal_mode. Los recursos se cierran explícitamente,
incluidos errores y ficheros ausentes; no se depende del recolector de basura.

En SQL, la guarda de aprobación usa `UPDLOCK, HOLDLOCK`, seguida de un UPDATE
condicional de la cola en la misma transacción y con la misma fábrica de
conexiones que el store de aprobación. Exige pending y decisión NULL. El UPDATE
exige claimed, propietario e intento originales, intento menor que tres,
updated_at original y fecha anterior al corte. OUTPUT debe devolver la identidad
y el intento esperados antes del commit. Un rechazo hace rollback. No existe una
segunda lectura después del commit que pueda atribuirse a otra generación.

La comparación exacta de updated_at invalida también una candidatura cuya
fecha haya cambiado sin cambiar de propietario. Usa los mismos valores FLOAT
persistidos; no introduce conversiones de precisión ni migración. Los relojes
de los hosts pueden adelantar/retrasar la selección. La seguridad del consumo
se apoya en las guardas, no en considerar el reloj una prueba de exclusividad.

## Evidencia y aceptación

- 79 casos nuevos: 54 runtime/SQLite y 25 de contrato SQL.
- Focal inicial: 75 PASS; tras añadir caída abrupta real y pruebas de commit,
  selección conjunta P4/P5/P6 y ciclo de conexiones: 157 PASS.
- Un subproceso reclama y termina con `os._exit(73)`: el commit permanece y
  otra instancia recupera la continuación antes del consumo HITL.
- SQLite en fichero compartido/separado y DELETE/WAL, approve/reject, carreras
  claim/recuperación y recuperación/recuperación, propietario reutilizado,
  timestamp alterado, exclusión de terminales y límite de tres intentos.
- El trabajador pausado que reaparece no responde al workflow ni notifica
  después del barrido. Se conserva su aprobación pending sin concederle claim.
- Fallo real inyectado antes/después del commit SQLite: rollback cuando aún
  corresponde, resultado incierto y detención del lote. Cierre verificado con
  referencias retenidas a conexiones, incluido fichero ausente.
- SQL: fábrica incompatible, autocommit activo/desconocido, errores de sentencias,
  lectura, commit y cierre; rechazo sin OUTPUT y sin adoptar otra generación.
- Linux FULL NON-LIVE: **3.641 passed, 24 deselected, 3 warnings**, 72,82 s,
  exit 0. Comparación de XML: conserva los 3.562 casos de P5 y añade los 79
  anteriores. No se suman los focales a la FULL. Aceptación Windows y publicación
  de P6 pendientes. No se ejecutan SQL real, agentes remotos, MCP, JWT ni Azure.

## Despliegue por cliente y pendientes

Se conserva Python + Microsoft Agent Framework para orquestación y agentes
especialistas. Este componente de gobierno es determinista: no requiere otro
agente, LangChain, A2A ni una decisión LLM. Mantiene la decisión de retirada del
diseñador del portal documentada en `foundry-workflow-retirement.md`.

El puerto es adicional: el worker y su recuperación local por excepción no
cambian de firma ni activan el barrido. Un adaptador externo sólo necesita
implementar la nueva capacidad si su host quiere consumirla.

Antes de activarlo en una instalación: todos los consumidores de aprobación
deben aplicar P5, retirar/drenar binarios anteriores, fijar política de antigüedad
y presupuesto operativo, observabilidad, cadencia y parada. Cualificar con SQL
real el driver, aislamiento, bloqueos, carreras, desconexiones y plan de consulta.
La fábrica común no acredita por sí sola la identidad ni el esquema desplegado.

No se recuperan automáticamente aprobaciones claimed/completed, efectos remotos,
notificaciones ni sesiones MCP. Presupuesto agotado y resultado incierto requieren
conciliación; no se resetean approvals, dispatch o ledgers. Outbox de comunicación,
turnos durables de sesión, afinidad de release y aislamiento multicliente siguen
abiertos. No se afirma exactly-once distribuido ni se cierra F37 o F27 LIVE.

## Referencias

Consultadas el 17/11/2026:

- [SQLite transactions](https://www.sqlite.org/lang_transaction.html): transacción
  de escritura y adquisición con BEGIN IMMEDIATE.
- [Microsoft SQL table hints](https://learn.microsoft.com/en-us/sql/t-sql/queries/hints-transact-sql-table?view=sql-server-ver17):
  duración y alcance de UPDLOCK/HOLDLOCK; no sustituyen la aceptación del servidor.
- [P5, claim HITL coordinado](e3-continuation-hitl-claim.md): condición previa para
  impedir que un intento sustituido responda al workflow.

Las fuentes fundamentan el diseño; los resultados de producto proceden de las
pruebas indicadas y deben mantenerse separados de la futura evidencia LIVE.
