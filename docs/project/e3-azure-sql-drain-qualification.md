# E3/P8/P12 R1. Cualificación de admisión y drenaje en Azure SQL

Base funcional: P11, commit 913feaf86b17ecd8b60b1ea452fb07edcbb67a21.
Estado: protocolo preparado offline. La ejecución en Azure SQL requiere autorización del destino y de las escrituras sintéticas.

## Preparación del ensayo

Usar una base de cualificación aislada, el controlador del proyecto y las rutas AzureSqlExecutionStore.admit, begin_drain y azure_sql_release_drain. Comprobar destino, esquema candidato de P9, tablas de inventario y permisos efectivos, autocommit=False y snapshot_isolation_state_desc=ON. Registrar la versión del controlador y el estado de READ_COMMITTED_SNAPSHOT por separado. Asignar dos instalaciones A/B, una versión N y claves de ejecución únicas por ensayo. Registrar el estado inicial. Separar creación de esquema, limpieza y ejecución de la prueba. El marcador de drenaje persiste; usar un ámbito nuevo en cada orden.

## Dos escritores sobre el ámbito A/N

Abrir conexiones físicas independientes y registrar sus @@SPID. En el arnés de prueba detener al líder después de leer la clave de drenaje con el bloqueo del adaptador y antes de confirmar. Enviar la operación rival sobre otra conexión. Usar una tercera conexión observadora para acreditar que el rival espera al líder en la consulta de drenaje. Liberar al líder y esperar ambos resultados con un plazo acotado. Una pausa temporal por sí sola no acredita solapamiento. Liberar siempre la barrera y cerrar las conexiones incluso ante error.

1. Admisión primero. El líder admite X y el rival inicia el drenaje. Tras ambos commits, reabrir el almacén: get_execution(X) y el reintento con el mismo contenido devuelven la asignación original. El informe P11 contiene X, con inicio sin confirmar si no se creó checkpoint. Una admisión nueva para A/N debe devolver AdmissionClosedError.
2. Drenaje primero. El líder inicia el drenaje y el rival intenta admitir Y. Tras el commit del líder, comprobar AdmissionClosedError, ausencia de Y al reabrir y marcador cerrado. Repetir begin_drain y verificar el mismo estado.
3. Aislamiento. En cada orden, admitir un incidente distinto para B/N tras cerrar A/N. Comprobar su persistencia y su ausencia en los bloqueos de A. Si se mide contención entre instalaciones durante la carrera, registrar la espera por separado de la decisión funcional de admisión.

## Lectura del informe durante un cambio confirmado

Usar otro ámbito A/N inicialmente abierto y sin bloqueos ni historial residual en la base aislada. Iniciar azure_sql_release_drain con page_size=1. Detener el lector justo después de obtener el marcador de admisión, dentro de la transacción SNAPSHOT. En una conexión distinta admitir Z y confirmar; después cerrar A/N y confirmar. Reanudar el lector original: debe observar admisión abierta y ausencia de Z. Un segundo informe en conexión nueva debe observar admisión cerrada y el bloqueo de Z. Comprobar los campos, porque ambos informes pueden devolver blocked por causas distintas.

## Evidencia y criterio de salida

Conservar por escenario el commit, los ámbitos sintéticos, sesiones, orden de barreras, bloqueo observado, commits o rollback, resultado tras reapertura e informes anterior y posterior. Registrar plazos excedidos, deadlocks, fallos de permisos o visibilidad insuficiente como ensayo inconcluso o fallido; conservar el primer resultado antes de cualquier repetición. La preparación offline cubre el contrato del adaptador y los órdenes en SQLite. La cualificación Azure SQL exige los tres escenarios anteriores y la lectura concurrente en el motor real. El resultado del ensayo no activa N+1.

Referencias: [bloqueos UPDLOCK y HOLDLOCK](https://learn.microsoft.com/en-us/sql/t-sql/queries/hints-transact-sql-table) y [aislamiento SNAPSHOT](https://learn.microsoft.com/en-us/sql/connect/ado-net/sql/snapshot-isolation-sql-server).
