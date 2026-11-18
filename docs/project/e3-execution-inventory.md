# E3 P8-P3 R1 · Inventario de ejecuciones y diagnóstico persistente

Candidato del 18 de noviembre de 2026 sobre P8-P2 publicado en `c14c077`.
Cada instalación puede obtener el mismo formato de informe con su afinidad de
consumidor. El código Python observa registros ya escritos por el runtime y
el SDK Microsoft Agent Framework. Las pruebas usan agentes sintéticos.

## Qué responde la consulta

La unidad de inventario es la admisión. Una alerta admitida sigue apareciendo
aunque nunca haya producido un checkpoint o una continuación. La afinidad de
la instalación procede de la configuración de operador. Una versión anterior
de la misma instalación aparece con `compatible=false`. El filtro de
instalación se aplica antes de paginar. Se exportan ID de ejecución, release,
huella, compatibilidad, estado observado, número de checkpoints con ID, contadores
por estado de aprobación y de ambas colas, e incidencias de correlación.

| Evidencia disponible | Interpretación |
| --- | --- |
| Admisión sin checkpoint, aprobación ni continuación | `start_unconfirmed`. El arranque sigue sin acreditarse. |
| Checkpoint con mensajes para el siguiente ejecutor | `in_progress`. Es el último estado observado en disco. |
| Solicitud con ID de recheck del contrato y estado de espera de validación | `wait_checkpoint`. Requiere una señal para continuar. |
| Espera humana con correlación durable | `hitl_checkpoint`. El contador distingue aprobación pendiente, reclamada o consumida. |
| Espera humana antes de registrar la correlación | `hitl_registration_unconfirmed`. Se conserva la incertidumbre sobre el registro. |
| Último checkpoint con estado terminal explícito, sin mensajes ni solicitudes | `terminal_checkpoint`. Un conflicto con trabajo pendiente produce `unresolved`. |
| Fin sin estado terminal acreditado, solicitud desconocida o cadena incoherente | `end_unconfirmed`, `pending_request_unidentified` o `unresolved`. Requiere conciliación. |

Los IDs de iteración y las marcas temporales pueden coincidir. El lector sigue
`previous_checkpoint_id`, exige una sola cadena con firma común y comprueba la
entrada nativa previa a la primera asignación de ID. El contador excluye esa
entrada. Las aprobaciones se concilian con los IDs de solicitud del checkpoint
registrado. La cola histórica se concilia por aprobación. Si está en otra base,
se exige también que coincidan workflow, solicitud y checkpoint en ambos
registros de aprobación. Una cola externa sin correlación independiente queda
como `unattributed_separate_store`. Si falta la cola implícita se devuelve
`unavailable`. El mismo trabajo presente en ambas colas genera una incidencia.

## Uso de operador con copias offline

En una copia coherente y ya existente de SQLite y del directorio
FileCheckpointStorage, usar el documento de afinidad completo del consumidor
verificado. Los ejemplos usan rutas relativas a la copia del operador.

```powershell
python -m src.review.execution_inventory --database .\state.db --checkpoints .\checkpoints --consumer-affinity .\afinidad.json --output .\inventario-01.json
python -m src.review.execution_inventory --database .\state.db --checkpoints .\checkpoints --store-residuals --output .\historico-almacen.json
```

La primera consulta acepta `--limit` de 1 a 100, con 50 por defecto. Si devuelve
`next_after`, pasar ese valor mediante `--after` con un nuevo archivo de salida
sobre la misma copia. Pasar `--legacy-database` si el archivo de cola histórica
es distinto. Ambos modos abren las bases existentes en lectura. La salida
incluye hora UTC de exportación. Se escribe un temporal en el directorio de
salida, se vacía a disco y se publica mediante un enlace físico exclusivo en
ese mismo volumen. El sistema de archivos debe admitir enlaces físicos. Un
nombre ya existente conserva su informe. Situar los informes fuera del árbol de
checkpoints y aplicar los permisos de operador correspondientes al directorio.

El segundo modo es administrativo para el almacén completo. Cuenta aprobaciones,
trabajos y checkpoints sin admisión atribuible. Distingue las entradas sin ID de
otros checkpoints sin ID. Algunos de estos contadores pueden corresponder a una
misma ejecución. Una entrada sin ID también puede pertenecer a una ejecución
admitida. El administrador obtiene totales, sin IDs ni asignación a clientes.
Esta consulta global requiere derechos sobre todas las fuentes inspeccionadas.
La CLI es de operador local. La afinidad selecciona el ámbito de consulta y la
autorización de acceso depende de los permisos sobre la copia.

## Codificación de checkpoints en disco

FileCheckpointStorage de la versión fijada escribe JSON en modo texto con la
codificación predeterminada de Python. En Windows puede depender de la
configuración del productor. El lector conserva la detección de JSON Unicode
UTF-8, UTF-16 y UTF-32. Si el contenido sin marca falla al decodificar como
UTF-8, prueba la codificación local de texto. Un error de sintaxis, una clave
duplicada o una marca Unicode dañada detienen la lectura.

Si conoces la codificación de origen, especialmente al trasladar un directorio
entre máquinas, puedes fijarla con `--checkpoint-encoding cp1252` (u otra
codificación acreditada) en cualquiera de los dos modos. Esa opción tiene
prioridad incluso si los bytes también forman UTF-8 válido. Un directorio con
orígenes mezclados necesita copias identificadas por codificación para que una
selección explícita sea válida para todos sus ficheros. El informe sigue en
UTF-8 y los checkpoints se conservan byte a byte.

## Coherencia y límites

- Las páginas se ordenan por ID de ejecución. Cada página tiene una transacción
  propia. Para comparar páginas, usar la misma copia inmóvil. SQLite, archivos y
  una base histórica separada tienen cortes independientes. Copiar un SQLite
  activo omitiendo su WAL puede perder evidencia.
- Un cursor obtiene lotes de 64 filas. SQLite recorre los JSON del directorio por
  página. La memoria del informe crece con la historia de las admisiones de la
  página. La revisión administrativa recorre el almacén y puede resultar costosa.
- El adaptador Azure SQL usa una conexión dedicada con autocommit desactivado,
  una transacción SNAPSHOT, parámetros ligados y rollback al terminar. Requiere
  las tablas candidatas, las históricas, permisos de lectura y aislamiento ya
  disponibles. Las pruebas ejercitan el contrato de consultas con un doble.
  Queda pendiente probar contra Azure SQL real, incluidos collation, planes,
  rendimiento, bloqueos y coherencia bajo concurrencia.
- Los lectores inspeccionan metadatos JSON y no restauran objetos serializados
  ni arrancan el workflow. Los informes omiten payloads, identidades de operador,
  errores en texto libre, contenido de alertas y secretos de transporte.
- Un checkpoint terminal acredita el estado observado. Todavía pueden faltar
  confirmación de efectos externos, notificación, cierre durable de la ejecución
  o trabajo posterior. También puede existir un efecto sin acuse tras una caída.
  Una página vacía o un informe administrativo a cero carecen por sí solos de
  valor como autorización de despliegue.

P8 sigue abierto. Quedan por resolver el cierre durable y la coordinación entre
el bloqueo de nuevas admisiones y el drenaje, los consumidores del host y la
cualificación con el almacén real. F27 LIVE continúa pausada.

[Admisión y colas](e3-execution-admission-queue.md) · [Afinidad](e3-release-affinity-contract.md) · [Roadmap](roadmap-f27-f48.md)
