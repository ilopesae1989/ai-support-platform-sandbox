# P8 · Cierre durable tras un rechazo humano

Primer incremento sobre f728dd9. El consumidor candidato registra el rechazo
terminal de una ejecución admitida después de que regrese el notificador.
Comprueba el resultado tipado ApprovalOutcome, el ID admitido, la afinidad,
la decisión negativa consumida y el propietario y generación del intento.
El cambio a completed y el recibo comparten transacción. Al reabrir el almacén,
rejection_closure devuelve el ID de aprobación del rechazo registrado.
La repetición exacta de esa escritura devuelve el trabajo ya completado.

La recepción externa de una notificación puede seguir siendo incierta aunque
el notificador haya retornado. Una caída después del consumo HITL y antes del
commit conserva esa incertidumbre. La consulta y la repetición de escritura
no reenvían notificaciones ni vuelven a procesar la decisión.

SQLite crea la tabla en su composición candidata. El SQL para Azure SQL se
entrega en candidates para revisión posterior junto con el esquema de admisión.
La cualificación en servidor y la activación quedan pendientes. Los históricos
conservan su estado sin backfill. Este recibo sólo cubre el rechazo humano del
flujo candidato. Quedan otros terminales, la integración del recibo en el
inventario y la coordinación transaccional de admisión y drenaje por instalación.
