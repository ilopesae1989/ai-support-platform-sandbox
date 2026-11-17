# Entrega 3 — procesamiento HITL y evidencia independientes del canal

Tercer paquete, 16/11/2026. Proyecto Creación de agentes.
Base publicada: `5a81ea8cbd37de0646691405a60c58fc32b2e8fd`, árbol
`bed080cbe8aff7883aac6b34c7e1d91632232ab2`. Se comprobaron los 24 blobs
publicados del segundo paquete y su avance de un commit sobre `897807a`.
Su aceptación Windows acredita 3.454 PASS, 24 excluidas y 3 avisos.

## Problema y resultado

El worker y la cola ya eran reutilizables, pero los procesadores de aprobación
simple e incidente completo seguían implementados dentro de Teams. Además,
Teams y el núcleo definían por separado `ApprovalDecisionEvidence` con los mismos
campos y validadores. Cambiar un formato podía dejar al otro atrás.

Los dos procesadores pasan al runtime. Teams transforma su invocación previamente
autenticada y autorizada en un contexto de identidad independiente del canal.
Los constructores de evidencia usan el modelo canónico que ya existía en
`runtime/procedure/approval_evidence.py`. Los puntos públicos de entrada Teams
se conservan como adaptadores; el bootstrap y el worker siguen usándolos.

El núcleo procesa aprobación o rechazo mediante el workflow nativo MAF y agentes
sintéticos. Una prueba en un proceso nuevo bloquea cualquier importación de
`src.channels` y `microsoft_teams` y completa un rechazo con evidencia y consumo.
No se cambia el lenguaje, framework, grafo, configuración de agentes o protocolo MCP.

## Cambios y justificación

| Frontera | Cambio y motivo |
| --- | --- |
| `runtime/procedure/approval_context.py` | Contexto inmutable de decisión e identidad; exige política y campos obligatorios exactos antes de consumir la aprobación |
| `channels/teams/approval_context.py` | Mapea tenant, principal Entra, usuario de canal y conversación de la invocación ya autorizada; fija canal y esquema de identidad desde el adaptador |
| `runtime/incident_approval_processor.py` | Reutiliza resolución, restauración, claim, respuesta y evidencia del incidente sin importar Teams |
| `runtime/procedure/approval_processor.py` | Extrae también el recorrido original de aprobación simple para no dejar dos políticas de reanudación en el canal |
| `runtime/procedure/approval_evidence.py` | Centraliza los dos constructores y el contrato de evidencia existente; conserva campos, validadores y representación JSON |
| Tres fachadas de Teams | Conservan nombres de funciones, resultados y error de evidencia; transforman la entrada y delegan, sin duplicar reglas |
| Dos suites existentes | Los spies pasan al núcleo; siguen entrando por la fachada Teams y comprobando orden, contexto y correlación. Se elimina raising=False para detectar un punto de parche inexistente |
| Fixture y pruebas nuevas | Acreditan JSON anterior, identidad, consumo monotónico, negativos y ejecución nativa sin canal |

## Identidad y autoridad

El nuevo contexto es un contrato interno. Su construcción no autentica al actor
ni concede autorización. La autenticación de Teams, el tenant esperado, la
correlación de identidad y la pertenencia al grupo permanecen en los componentes
anteriores, sin modificar su código ni exponer un endpoint nuevo.

La acción conserva sólo approval_id y decisión. Workflow, request y checkpoint
se resuelven desde el pending store; la operación continúa en el estado gobernado
original. El contexto no acepta destino, capability ni parámetros operacionales.
La conversación del checkpoint debe coincidir con la identidad suministrada por
el adaptador antes del claim.

El tenant del contexto es identidad para correlación/evidencia; este cambio no
crea una autorización de acceso a datos de otros clientes. El despliegue sigue
seleccionando sus stores y políticas. Otro canal real necesitará su adaptación
autenticada/autorizada y aceptación propia; el canal alternativo de prueba es
sintético y no forma parte de los endpoints productivos.

## Orden de ejecución conservado

Incidente completo:

1. Resolver la correlación técnica desde el store.
2. Restaurar y verificar la solicitud HITL exacta y su conversación.
3. Recuperar el contexto seguro de comunicación del checkpoint exacto.
4. Consumir la aprobación mediante claim y verificar la correlación reclamada.
5. Entregar una respuesta booleana a MAF.
6. Exigir un único resultado, sin solicitudes nuevas, y comprobar correlación.
7. Construir evidencia de la decisión humana y completar la aprobación.

En la aprobación simple se conserva el comportamiento del resumer original:
completa el consumo después de validar su resultado y el procesador construye
la evidencia a continuación. Esta diferencia existente entre recorridos no se
oculta ni se altera en una extracción. No se añade atomicidad entre evidencia,
consumo, resultado y notificación.

La evidencia describe quién decidió y bajo qué política; una decisión approve
no demuestra por sí sola el éxito técnico de la operación. El resultado y sus
postcondiciones mantienen sus contratos independientes.

## Compatibilidad y pruebas

El fixture `tests/fixtures/approvals/evidence_before_e3_p3.json` se generó con el
código publicado anterior, decisiones sintéticas approve/reject y reloj fijo.
Ambas evidencias nuevas coinciden campo a campo con su JSON histórico. Se
conservan las importaciones de `ApprovalDecisionEvidence` y del error desde
Teams mediante alias al contrato canónico. No se introduce un formato de
persistencia nuevo ni una migración genérica de objetos pickle externos.

Focal existente: **618 passed, 1 warning**. Suite nueva: **28 passed**:

- mapeo exacto de identidad y política, y JSON histórico de ambas decisiones;
- rechazo de entradas no adaptadas, identidad ambigua y correlación alterada;
- aprobación y rechazo del workflow nativo con agentes sintéticos, consumo
  persistido en SQLite y rechazo del replay sin nuevas invocaciones de agentes;
- conversación distinta y contexto comunicable ausente bloquean el claim;
- siete fallos posteriores al claim mantienen consumo y bloquean otra respuesta;
- proceso nuevo con importaciones de canal prohibidas.

Regresión completa Linux: **3.482 passed, 24 deselected, 3 warnings**, 81,11 s,
exit code 0. Conserva los 3.454 casos anteriores y añade los 28 indicados.
Windows: pendiente para este tercer paquete. Los focales no se suman a la FULL.

La prueba nativa usa Agent Framework real y agentes simulados. SQLite acredita
el consumo local observado; no sustituye pruebas de aislamiento/concurrencia
del Azure SQL desplegado. No se ejecutan servicios Foundry, herramientas MCP,
operaciones Azure, despliegues ni migraciones. No se actualizan dependencias.

## Estado y siguiente trabajo

IDs conservados: F30-T03/T04 y apoyo F37/F40 en el alcance de evidencia de la
decisión. No se cierran F30/F31/F37 ni la entrega 3 completa.

La extracción del procesamiento HITL queda implementada en este candidato.
Continúan las ventanas ya documentadas: trabajos claimed abandonados por caída
dura, notificación recuperable, exclusión de turnos de sesión, afinidad de release
y recuperación remota. El siguiente paquete debe concretar la recuperación de
trabajos huérfanos, preservando aprobación y dispatch consumidos y delimitando
las pruebas que necesitan SQL real de ensayo. No se añade otra fase al roadmap.

Reversión: volver al código previo manteniendo el formato Teams y las tablas
actuales. No borrar aprobaciones, trabajos ni ledgers para facilitar el rollback.
