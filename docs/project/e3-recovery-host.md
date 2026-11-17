# Entrega 3, P7 R1 — integración opcional de recuperación en el host

Fecha: 17/11/2026. Proyecto Creación de agentes. Incremento de F30/F31.
Base publicada: `56b8c67f5cca4e297b9600f1c651b354008b979e`.
Árbol base: `247d1d515169e80c4536400fccba54e437b08606`.
P6 R1 obtuvo 3.641 PASS tanto en Windows como en Linux y está publicado.

Actualización posterior: P7 fue aceptado en Windows con 3.703 PASS, 24 excluidas,
3 avisos, y publicado en `55927f1ff420e5d29bf16eabb592a297aa3987c8`.
El árbol coincide con el candidato Linux: `0530acc2843dd93ad3fc50c99e301201e551eb84`.
El siguiente contrato se documenta en [E3-P8-R1](e3-release-affinity-contract.md).

## Decisión y secuencia acotada

P6 proporciona recuperación transaccional explícita, pero ningún consumidor
del ciclo del host. P7 conecta ese servicio a los hosts local y productivo,
con una política de instalación obligatoria para activarlo. Sin configuración
el comportamiento previo se conserva y no se construye ni ejecuta recuperador.

1. Verificar la base y leer composición, arranque, parada y contrato P6.
   Justificación: reutilizar la pareja de stores del worker, sin un segundo
   proveedor ni una nueva autoridad de aprobación.
2. Validar configuración explícita antes de construir proveedores. Evita un
   valor por defecto que habilite transiciones en instalaciones existentes.
3. Integrar un runner neutral en el TaskGroup del host. Hace que su vida útil
   y parada pertenezcan al proceso que ya administra app y worker.
4. Probar límites, paginación, incertidumbre, cancelación, composición y
   separación de instalaciones con pruebas NON-LIVE; ejecutar regresión completa.
5. Entregar parche y validación Windows contra el árbol exacto. Aceptar la
   evidencia Windows antes de preparar publicación; no desplegar ni activar.

La lógica es Python determinista. Se conservan Microsoft Agent Framework,
agentes especialistas Foundry y selección READ/WRITE existentes. Este componente
no requiere LLM, agente adicional, LangChain, A2A ni migración del SDK. Permanece
vigente `foundry-workflow-retirement.md`: la retirada del diseñador del portal
no convierte el WorkflowBuilder de Python en una dependencia retirada.

## Configuración por instalación

La única entrada nueva es `CONTINUATION_RECOVERY_JSON`, leída del mapping del
host. Su ausencia desactiva la recuperación; una cadena vacía o JSON incorrecto
impide el arranque. También se admite la desactivación explícita:

```json
{"schema":"continuation-recovery-v1","enabled":false}
```

Ejemplo ilustrativo de activación, **sin aprobación para aplicarlo en Azure**:

```json
{
  "schema": "continuation-recovery-v1",
  "enabled": true,
  "min_claim_age_seconds": 300,
  "interval_seconds": 60,
  "batch_size": 25,
  "max_batches_per_cycle": 4
}
```

Los cuatro valores son obligatorios al activar. La versión v1 acepta enteros
exactos: edad e intervalo entre 1 y 86.400 segundos; tamaño de página y páginas
por ciclo entre 1 y 100. Los límites acotan la configuración soportada y hasta
10.000 candidaturas por ciclo. El ejemplo no establece el TTL de producción.
Se rechazan booleanos como enteros, floats, strings numéricos, claves duplicadas,
campos desconocidos y schemas futuros. Al desactivar solo se aceptan schema y
enabled para evitar configuraciones parcialmente ignoradas.

La política viene del despliegue de ese cliente, nunca de una alerta, un mensaje
Teams, un ticket o el contenido de la aprobación. Se adjunta después de componer
el host y reutiliza exactamente `continuation_store` y `store`, conservando
el resto del bootstrap, incluido `session_store` productivo. La composición
no abre conexiones ni ejecuta recuperación. Las tres fábricas productivas,
con o sin resolución de identidad entre tenants, tienen la misma integración.

No se añaden parámetros Bicep, secretos, esquema SQL ni cambios en Azure. La
fábrica de instalaciones debe transportar esta configuración en una entrega
posterior y acreditar versión, stores, aislamiento y política de cada cliente.
Dos bases separadas con el mismo approval_id no interfieren en la prueba local;
esto no acredita aislamiento de tenants en una base compartida ni en Azure.

## Ciclo de vida, límites y recuperación

- El runner comienza con el host solo si existe política habilitada. No se
  comparte ni reinicia una misma instancia; una segunda llamada a run falla.
- Cada barrido fija `max(0, reloj Unix - edad)` una vez. Selecciona páginas con
  el cursor exclusivo del motor y conserva corte/cursor entre ciclos limitados.
  Así una primera página de candidaturas rechazadas no bloquea las siguientes.
- Cada ciclo tiene como máximo las páginas configuradas. Espera el intervalo
  después de ese ciclo. Al completar el barrido, el siguiente empieza sin cursor
  y con un corte nuevo. No es una instantánea global ni un recorrido persistido;
  las filas nuevas anteriores al cursor se revisan en el siguiente barrido.
- Los lotes son secuenciales y reutilizan todas las guardas P5/P6. No hay
  solapamiento dentro de una instancia. Varias réplicas pueden competir; la
  exclusión válida sigue siendo la transacción y el intento, no este temporizador.
- Cada lote síncrono se ejecuta en `asyncio.to_thread`, sin ocupar el event loop
  con esa llamada. El host conserva una referencia a la tarea y espera bajo
  `asyncio.shield`. Una cancelación, incluso repetida, se propaga **después** de
  recoger el resultado o error del lote ya enviado. No se lanza otro lote.
- La señal de parada se comprueba antes de cada lote y corta la espera de
  intervalo. Si llega durante un lote, se termina ese lote y se informa su
  resultado. No interrumpe la transacción ni cancela candidatos a mitad de página.
- Error de reloj, error de selección/lote o resultado `uncertain` detiene ese
  recuperador, con `halted=True`. No reintenta, relee para adoptar autoridad ni
  avanza cursor. App y worker mantienen su ciclo normal; no se fuerza un reinicio
  del proceso como reacción automática a la incertidumbre del recuperador.

La detención es un estado **en memoria**, no una cuarentena durable. Un proceso
nuevo con la misma configuración habilitada crea otro runner. Tras incertidumbre,
operación debe desactivar la recuperación y conciliar antes de reactivarla. P7
no garantiza parada global entre réplicas ni reanudación persistida del cursor.

La cantidad acotada no establece un máximo de duración SQL. Al cancelar puede
haber que esperar a que termine el driver; no se promete shutdown con plazo duro.
SIGKILL o caída del host no pueden drenar. La aceptación con SQL real debe
verificar timeouts, bloqueos, desconexiones y el margen de terminación del host.
No se interpreta antigüedad como prueba de muerte del worker.

## Observabilidad

Cada ciclo emite `continuation_recovery_cycle`, con número de ciclo, lotes,
candidaturas, reencoladas, rechazadas, inciertas, motivo, tipo de error y halt.
Los valores agregados aparecen en el mensaje y en campos del LogRecord.
Los ciclos normales usan INFO y las detenciones por error ERROR. La instalación
debe configurar el logger `src.runtime.incident_continuation_recovery_runner`
al nivel INFO y recoger ERROR para alertar; P7 no modifica el logging global.
`last_cycle` y `halted` permiten inspección dentro del host. La última muestra
es de ciclo, no una prueba de salud en Azure ni un registro durable de auditoría.

No se registran approval_id, worker_id, cursor, payload, tokens ni texto crudo de
excepciones. Los rechazos conservan las guardas; requeued significa confirmación
de la transición recibida, no ejecución del procedimiento ni cierre del incidente.

## Cambios y justificación

| Archivos | Cambio y motivo |
| --- | --- |
| `src/config/continuation_recovery.py` | Parser estricto y opt-in; impide activar por configuración ambigua |
| `src/runtime/incident_continuation_recovery_runner.py` | Planificación neutral, límites, observación y drenaje de lote |
| `src/channels/teams/recovery_composition.py` | Adjunta recuperación a la pareja de persistencia del host sin abrirla |
| `src/channels/teams/bootstrap.py` | Campo opcional keyword-only, compatible con la subclase productiva |
| `src/channels/teams/production_composition.py`, `src/production_composition.py` | Validación antes de proveedores y conexión de las fábricas existentes |
| `src/channels/teams/main.py`, `src/channels/teams/production_runtime.py` | Tarea opcional dentro del TaskGroup y señal de parada compartida |
| `tests/config/test_continuation_recovery.py` | Rechazo de configuración inválida y compatibilidad desactivada |
| `tests/runtime/test_incident_continuation_recovery_runner.py` | Corte/cursor, límites, errores, cancelación repetida y dos instalaciones SQLite |
| `tests/channels/teams/test_recovery_host.py` | Arranque/parada, fallos del host, pareja exacta y todas las composiciones |
| `tests/channels/teams/test_production_host_composition.py` | Admite solo el envoltorio de recuperación, conservando la guarda del selector |
| Este documento, `e3-continuation-recovery.md`, `roadmap-f27-f48.md` | Evidencia P6 y alcance P7, sin alterar fases/IDs ni declarar cierres pendientes |

## Evidencia y pendientes

Linux FULL NON-LIVE: **3.703 PASS**. 24 excluidas. 3 avisos. 75.64 s.
exit 0; Python 3.14.10. El XML conserva los 3.641 casos de P6 y añade
62 casos. Selección ampliada final: 183 PASS. No se suman
los focales a la FULL. Los tres avisos son los ya existentes en P6.
El primer focal obtuvo 73 PASS y 3 FAIL por una aserción de pruebas que confundía
el nombre público enabled con contenido de configuración. Se corrigió la aserción.
La selección ampliada obtuvo 181 PASS y 2 FAIL porque la guarda AST esperaba
retorno directo del bootstrap. Se actualizó para exigir el envoltorio exacto
y seguir comprobando el mismo delegado y selector. Se conservan ambos informes.

Windows y publicación de P7 aceptados según la actualización anterior. SQL real,
activación por cliente, observabilidad desplegada y aceptación del ciclo de cierre
en Azure permanecen pendientes.
Antes de activar: todos los consumidores deben usar P5, drenar binarios antiguos,
validar stores/identidades, definir la política y cualificar las carreras SQL.

Entrega 3 sigue abierta. No cierra F30/F31/F37 ni F27 LIVE. No recupera efectos
remotos, notificaciones, sesiones MCP, outbox, afinidad de release ni turnos
durables de sesión. Los pendientes de entregas 4–8 y F28–F48 se conservan.

## Referencias

- [Python 3.14: TaskGroup, cancelación, shield y to_thread](https://docs.python.org/3.14/library/asyncio-task.html),
  consultado el 17/11/2026. Fundamenta la supervisión de tareas y la propagación
  de cancelación después de la limpieza; la prueba del drenaje es local.
- [Contrato P6](e3-continuation-recovery.md): límites, incertidumbre y transacción.
- [Claim coordinado P5](e3-continuation-hitl-claim.md): consumo ligado al intento.
- [Plan F27–F48](roadmap-f27-f48.md): fases y aceptación pendientes.
