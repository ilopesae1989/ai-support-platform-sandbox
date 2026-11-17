# Entrega 3 — claim HITL ligado al intento de continuación

E3-P5-R2, 17/11/2026. Base publicada:
`a54050897f354acae94f9ed3dd25452f5f38ec3a`, árbol
`5648705188bfc1d2df5e11618b5bb2996fbe5841`.
Incremento NON-LIVE dentro de F30/F31 y la entrega 3; no añade fases.

## Problema y criterio

P4 impedía que un intento antiguo completara o fallara la fila de un intento
nuevo, pero entregaba al procesador el almacén de aprobación sin vincularlo al
claim de continuación. Se reprodujo con P4: el intento 1 se recupera, el mismo
propietario reclama el 2 y el trabajador anterior consume la aprobación y emite
una respuesta y notificación simuladas. Al completar la cola devuelve
`CLAIM_LOST`, demasiado tarde para impedir aquellos efectos.

El nuevo criterio es comprobar propietario y generación junto al consumo de
aprobación, antes de que el procesador entregue una respuesta al workflow.
La invocación persistida conserva la decisión humana; no se reconstruye
autoridad leyendo el intento vigente después de un rechazo.

## Cambios y justificación

| Cambio | Razón y consumidor |
| --- | --- |
| `ContinuationApprovalStore` por intento | El worker entrega al procesador una vista del mismo puerto de aprobación, restringida al approval_id, propietario, generación y decisión originales |
| `claim_approval` en el puerto de continuación | Define el consumo coordinado que deben implementar los adaptadores; no existe fallback al claim sin comprobación |
| Adaptador SQLite | Abre los ficheros existentes en una conexión, adjunta la aprobación si está separada y comienza `BEGIN IMMEDIATE` antes de comprobar ambos estados |
| Recovery SQLite en esa misma frontera | Evita comprobar pending en una conexión y actualizar después en otra, con una ventana entre ambas acciones |
| Adaptador Azure SQL | Usa una transacción con orden aprobación y después continuación, igual al recovery existente, y exige la misma fábrica de conexiones y autocommit desactivado |
| Tratamiento de error del worker | Desde que se intenta el claim, cualquier error impide reencolar por una relectura de pending; el commit puede haber ocurrido sin que llegara su confirmación |
| Contratos de composición y cierre | La ubicación SQLite y la identidad de fábrica SQL permiten comprobar la pareja configurada; pruebas verifican cierre en éxito y error |

La vista delega las lecturas de correlación y el complete de la aprobación al
store configurado. No admite registrar aprobaciones, cambiar de approval_id ni
completar desde esa vista sin haber recibido antes un claim confirmado. El core
de aprobación conserva restore, verificación de conversación/checkpoint,
correlación exacta, respuesta booleana MAF y evidencia. Teams sigue adaptando
la entrada autenticada; no se añade un endpoint ni un mecanismo de autenticación.

## Transacciones y concurrencia

SQLite conserva los ficheros actuales. Usa rutas URI escapadas y `mode=rw` para
adjuntar únicamente el fichero existente; los nombres de esquema son constantes.
Si cola y aprobación comparten fichero, utiliza `main` y no lo adjunta otra vez.
El claim escribe sólo la aprobación; recovery escribe sólo la cola. Cada uno
retiene la transacción durante sus comprobaciones y escritura, hasta el commit.
No se necesita una escritura atómica sobre dos ficheros modificados a la vez.
No se cambia journal_mode, esquema ni ubicación. Se prueban DELETE y WAL.

Azure SQL retiene los bloqueos `UPDLOCK, HOLDLOCK` de la aprobación y de la fila
de continuación. Sólo actualiza una aprobación pending con decisión NULL si la
fila sigue claimed por el propietario e intento esperados y la decisión coincide
con el payload persistido. El resultado no se devuelve al procesador hasta
después del commit. Un rechazo o excepción hace rollback y cierra recursos;
no hay reintento interno ni adopción de otra generación.

Las transacciones contienen sólo acceso a persistencia. No retienen bloqueos
durante restauración MAF, llamadas a agentes, respuesta al workflow o notificación.
Una vez consumida la aprobación, recovery debe rechazarla; no se habilita una
segunda respuesta por restaurar un checkpoint anterior.

## Evidencia

- Contraejemplo P4 reproducido en SQLite con callbacks sintéticos: se consumió
  la aprobación después de sustituir el intento y antes del rechazo de la cola.
- **45 casos nuevos**: 31 en runtime/SQLite y 14 de contrato Azure SQL.
- MAF real con agentes simulados: approve/reject válidos y sustitución del intento
  entre restauración y claim. El intento sustituido no consume la aprobación.
- SQLite: carreras claim/recovery, bloqueo comprobado entre lectura del
  propietario y commit, mismo propietario reutilizado, bases compartidas y
  separadas, DELETE/WAL, decisión distinta, alcance de approval_id, fichero
  ausente, rutas especiales y cierre de conexiones.
- Fallo de confirmación de claim antes/después de una escritura simulada:
  el worker no responde, notifica ni reencola, aun si la lectura devuelve pending.
- SQL: orden de bloqueos, propietario/generación, pending/NULL, decisión,
  ausencia de OUTPUT, identidad de fábrica, autocommit y fallos de cada sentencia
  y del commit. Son dobles; no demuestran los bloqueos del servidor desplegado.
- Linux FULL: **3.562 passed, 24 deselected, 3 warnings**, 79,04 s, exit 0.
  Conserva los 3.517 casos anteriores y añade los 45 indicados. Resultado R1.
- Windows R1: **3.561 passed, 1 failed, 24 deselected, 3 warnings**, 139,42 s,
  exit 1. Se conserva el XML `E3_P5_R1_WINDOWS_20261117_113032.xml`, SHA256
  `55d59e7075d9e455e614ba0d31c2dc0acd9a43864accc3c5a80667a24e028b2a`.
  Los 3.517 casos de P4 están presentes; los 45 nuevos coinciden con Linux.

### Corrección R2 del cierre en la preparación de pruebas

La prueba de fichero ausente falla al borrar `approval.db`, antes de llamar al
claim: `WinError 32`. El helper `setup` usaba `with sqlite3.connect(...)` para
configurar journal_mode. Ese contexto termina la transacción pero no cierra la
conexión. Se añade `contextlib.closing` conservando el contexto transaccional.
La comprobación local con referencias retenidas y GC desactivado encontró dos
conexiones abiertas en R1 y cero en R2. No se elimina ni se omite el caso.
No cambia el código de producto, dependencias ni contrato de recuperación.
Actualización 17/11/2026: Windows R2 completado con **3.562 PASS, 24 deselected,
3 warnings**, 117,27 s, exit 0, Python 3.14.2. XML
`E3_P5_R2_WINDOWS_20261117_120346.xml`, SHA256
`e6ebf10c61bd3598e866ef9c81c4c5c0b2a126b281db8d72357e9dd242c4155b`.
Publicado y verificado en `148ff9dcb4e73f23ea66059c75c6c1b26ef470fb`, único padre
`a54050897f354acae94f9ed3dd25452f5f38ec3a`, árbol
`d0f2a9b9814c82415ceb8d0a0ad83be29d02a90f`. Conserva 3.517 casos previos y añade 45.
Linux FULL R2: **3.562 passed, 24 deselected, 3 warnings**, 73,75 s, exit 0;
se conserva exactamente la selección de casos Linux R1.

Referencia: [Python sqlite3, contexto de conexión](https://docs.python.org/3.14/library/sqlite3.html#how-to-use-the-connection-context-manager).

La revisión solicitada sobre la retirada de workflows queda documentada en
[Foundry workflows: alcance y decisión](foundry-workflow-retirement.md).
Se mantiene el grafo Python de Agent Framework; no se introduce una dependencia
del diseñador visual de Foundry que se retira el 1/12/2026.

El focal SQL inicial tuvo un fallo en la comparación textual de espacios dentro
de los hints; se corrigió el normalizador del test y sus 14 casos pasaron antes
del cierre de la FULL. No se modificó producto para ocultar ese fallo.

## Compatibilidad, despliegue y límites

No se modifican tablas, JSON, versiones de agentes, SDK, framework, A2A ni MCP.
Las firmas anteriores de `PendingApprovalStore` permanecen. El puerto de
continuación añade el claim coordinado; un adaptador externo debe implementarlo.
El procesador inyectado debe consumir el store recibido por el worker. El acceso
directo a otro store desde código de confianza quedaría fuera de esta frontera.
La pareja de stores es configuración de confianza, no aislamiento multicliente
acreditado mediante un approval_id o una ruta de fichero.

No se certifica convivencia con binarios anteriores: requieren drenaje y retirada
para aplicar el contrato en todos los consumidores. El rollback de código conserva
datos y consumo, pero elimina esta protección; no resetear aprobaciones o ledgers.

No hay lease, TTL, reaper ni recuperación automática de un proceso muerto. Un
fallo después del consumo sigue requiriendo conciliación sin repetir la operación.
La notificación todavía precede a completar la cola; outbox recuperable, turnos
de sesión, afinidad de release y recuperación remota siguen abiertos.
El resultado incierto de un claim se bloquea; no se afirma resolver todos los
commits inciertos del resto de stores. No se acredita exactly-once distribuido.

El siguiente incremento, [P6: recuperación por lotes explícitos](e3-continuation-recovery.md),
añade selección y transición sobre esta frontera sin considerar un timeout
prueba de muerte. Su integración automática en el host y la aceptación SQL real
siguen separadas; no cambian retrospectivamente el alcance de P5.
No se cierra la entrega 3, F30/F31/F37 ni F27 LIVE, que permanece pausada.

## Fuentes de la decisión

Consultadas el 17/11/2026:

- [SQLite ATTACH](https://www.sqlite.org/lang_attach.html): alcance de las bases
  adjuntas y limitación de commit con varios ficheros modificados bajo WAL.
- [SQLite transactions](https://www.sqlite.org/lang_transaction.html): adquisición
  anticipada mediante BEGIN IMMEDIATE y comportamiento de transacciones.
- [Microsoft SQL table hints](https://learn.microsoft.com/en-us/sql/t-sql/queries/hints-transact-sql-table?view=sql-server-ver17):
  alcance de UPDLOCK/HOLDLOCK. Se conserva el orden de locks del recovery existente.

Estas fuentes fundamentan el diseño. La aceptación del producto procede de sus
pruebas y mantiene separado el SQL real aún no ejecutado.
