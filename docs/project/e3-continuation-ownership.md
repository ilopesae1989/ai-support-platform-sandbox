# Entrega 3 — propiedad por intento de continuación

Paquete E3-P4-R1, 17/11/2026. Base publicada:
`2659416ff59febe3bac2e11ae13d9312e224d5ec`, árbol
`e9fbee5539502e878f39b320e45a0fb80bfdbde9`.
Alcance NON-LIVE dentro de la entrega 3, preparación de F30-T02/T03/T04 y
F31-T02/T03/T04. P4 validado en Windows: **3.517 passed, 24 deselected,
3 warnings**, 133,45 s, Python 3.14.2, exit code 0. Informe
`E3_P4_R1_WINDOWS_20261117_082912.xml`, SHA256
`e060e1648ba443b8a9dfbb1a3b60e2973cc387d335ef1e32b0952649cb053628`.
Publicado en `a54050897f354acae94f9ed3dd25452f5f38ec3a`, árbol
`5648705188bfc1d2df5e11618b5bb2996fbe5841`; parent, árbol completo, 14 paths y
estadísticas contrastados con GitHub. La frontera HITL se aborda en
[P5](e3-continuation-hitl-claim.md); los límites siguientes describen P4.

## Problema reproducido

El bootstrap usaba el mismo `worker_id` para todos los hosts. Los métodos de
cola comprobaban `claimed_by`, pero no `attempt_count`. Con el código publicado
se reprodujo en SQLite esta secuencia: un trabajador reclama el intento 1,
lo devuelve a pending antes del consumo de aprobación, el mismo identificador
reclama el intento 2 y una llamada antigua a `complete` completa ese intento 2.
La comprobación del propietario por sí sola no distingue ambas ejecuciones.

Antes de introducir vencimientos o recuperar trabajos huérfanos, las mutaciones
de la cola deben conservar la generación que devolvió `claim_next`. Este paquete
cierra esa condición previa; no implementa un recuperador automático.

## Cambios y justificación

| Cambio | Motivo y límite |
| --- | --- |
| Identificador aleatorio por objeto de dependencias del worker | Evita compartir por defecto el propietario entre hosts. Permanece estable durante su vida; el bootstrap deja de fijar el valor común |
| `expected_attempt_count` obligatorio en `complete`, `fail` y `recover_claimed_before_approval` | El consumidor debe pasar el intento original, incluso si se reutiliza un identificador de trabajador |
| Condición de UPDATE por approval_id, estado claimed, propietario e intento | SQLite y Azure SQL rechazan una transición antigua sin cambiar la fila del intento vigente |
| Validación del intento antes de acceder al almacén | Rechaza valor ausente, booleanos, cadenas, flotantes, cero y negativos; no infiere el intento vigente |
| Máximo de tres intentos también dentro del UPDATE de recuperación | Conserva el presupuesto existente del worker y evita eludirlo llamando directamente al adaptador |
| Resultado `CLAIM_LOST` y propagación del intento en todos los caminos del worker | Si otro intento posee la fila, el trabajador anterior no la falla, completa ni vuelve a encolar. No adopta una generación obtenida mediante una lectura posterior |
| Pruebas y actualización de consumidores directos | Comprueban la frontera en SQLite real y los parámetros/transacciones del adaptador SQL sin acceder a Azure |

La generación es una precondición de concurrencia interna, no una credencial.
La autorización continúa en el checkpoint, el procedimiento y la aprobación.
Un consumidor no puede obtener autoridad leyendo `get()` y copiando el nuevo
intento a una llamada rechazada: debe conservar el resultado de su propio claim.

## Contrato y compatibilidad

Las tres mutaciones exigen ahora el argumento nombrado
`expected_attempt_count=claimed_job.attempt_count`. No hay valor por defecto ni
ruta legacy que omita la condición. Se actualizan todos los consumidores
directos del repositorio. Un adaptador o consumidor externo deberá implementar
este contrato antes de actualizar su host.

Se conservan el JSON de invocación, sus codecs, las columnas y los índices.
No se introduce TTL, heartbeat, lease, barrido de claimed ni migración SQL.
Los trabajos históricos siguen siendo legibles. El test de compatibilidad usa
una fila histórica sintética: no autoriza a un host nuevo a apropiarse de un
trabajo abandonado por otro proceso.

El orden del worker sigue siendo procesar, notificar y completar la cola.
Ante un error sólo se recupera la fila si la aprobación sigue pending y sin
decisión, con el presupuesto original. El adaptador SQL conserva su relectura
de aprobación y bloqueos dentro de la transacción. SQLite conserva su chequeo
en el almacén de aprobación separado. La cancelación deja el trabajo claimed
y se propaga; un reinicio no lo devuelve automáticamente a pending.

## Pruebas y evidencia

- Contraejemplo ejecutado con P3: una llamada del intento 1 pudo completar el 2
  con el mismo propietario. Sólo SQLite local, sin agentes ni servicios.
- 35 casos nuevos: intento antiguo, propietario diferente, carreras entre dos
  transiciones, reapertura, presupuesto, argumentos inválidos, worker obsoleto,
  cancelación, identidad de hosts y compatibilidad del payload histórico.
- Regresión Linux completa: **3.517 passed, 24 deselected, 3 warnings**, 70,03 s,
  exit code 0. Se conservan exactamente los 3.482 casos anteriores y se añaden 35.
- Entorno Linux: CPython 3.14.10; Agent Framework core 1.13.0 y Foundry 1.10.4.
  No se modifican dependencias del repositorio. Windows: aceptado según el
  recibo indicado al inicio de este documento.

Las carreras usan conexiones SQLite independientes. Las pruebas Azure SQL usan
dobles de conexión/cursor: acreditan el WHERE, los parámetros, rollback ante
OUTPUT vacío y cierre de recursos, no los bloqueos del servidor desplegado.
No se ejecuta una operación Foundry/MCP, Azure, despliegue ni migración.

## Límites y siguiente incremento

La propiedad protegida aquí es la fila de continuación. No se adquiere un fence
atómico entre esa propiedad y el claim HITL separado. Un worker obsoleto todavía
puede llegar al procesador o a la notificación antes de que la cola rechace su
finalización. No se acredita exactly-once, recuperación remota ni exclusión de
efectos operacionales mediante este cambio.

Por ello siguen pendientes el protocolo coordinado entre propiedad y consumo de
aprobación, el recuperador de huérfanos con sus criterios de abandono, y su prueba
con SQL real de ensayo. SQLite usa ficheros separados para cola y aprobación;
no se debe atribuir atomicidad distribuida a esas dos operaciones.

También siguen abiertos la notificación recuperable/outbox, la exclusión de
turnos, afinidad de release y recuperación de estado remoto. F27 LIVE permanece
pausada. No se cierra F30, F31, F37 ni la entrega 3.

Para un despliegue futuro hay que retirar o drenar los consumidores antiguos
antes de asumir esta protección: un binario anterior no aplica el nuevo WHERE.
Un rollback de código conserva tablas y payload, pero elimina esta protección
de generaciones; no se certifica una convivencia arbitraria de releases.
Nunca se borran trabajos ni se resetea una aprobación para facilitar el rollback.

## Referencia y decisión

Microsoft documenta la concurrencia optimista mediante UPDATE condicionado a los
valores originales y la detección de conflictos cuando no se modifica ninguna
fila: [Optimistic concurrency](https://learn.microsoft.com/en-us/sql/connect/ado-net/optimistic-concurrency?view=sql-server-ver17),
consultado el 17/11/2026. Se aplica ese patrón al propietario y generación ya
existentes; no requiere cambiar de Python o Microsoft Agent Framework ni añadir
otro protocolo A2A. La referencia fundamenta el patrón, no certifica las
transacciones ni la recuperación LIVE de este producto.
