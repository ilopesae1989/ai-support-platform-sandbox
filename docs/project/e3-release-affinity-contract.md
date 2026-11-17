# Entrega 3, P8 R1 — identidad de release y contrato de afinidad

Fecha: 17/11/2026. Proyecto Creación de agentes.
Base publicada: `55927f1ff420e5d29bf16eabb592a297aa3987c8`.
Árbol base: `0530acc2843dd93ad3fc50c99e301201e551eb84`.
P7 aceptado Linux/Windows con 3.703 PASS; publicado y verificado.

## Alcance exacto

Primer paquete de implementación del punto 8 de entrega 3. P8 completo comprende
identidad, asignación durable del incidente, selección de cola, recuperación,
diagnóstico y drenaje. Este paquete implementa la identidad y su primer consumidor
neutral, la construcción/restauración del workflow. **No cierra P8 ni la entrega 3.**

La revisión previa demostró que cambiar Foundry provoca un rechazo de checkpoint
después del claim de cola, con posible agotamiento de tres intentos. También que
cambiar el registro de procedimientos puede conservar la firma estructural MAF.
R1 refuerza la identidad del grafo; **todavía no cambia el selector ni el presupuesto
del worker**. No se considera resuelto el primer problema.

El punto de entrada `build_production_application` rechaza la presencia de las
claves de activación de afinidad antes de construir proveedores. Esto impide
presentar como desplegable un contrato cuya integración durable está pendiente.
Los consumidores de laboratorio pueden usar la fábrica neutral de forma explícita.
La configuración productiva histórica, sin esas claves, conserva su recorrido.

## Cambios y justificación

| Área | Cambio | Motivo |
| --- | --- | --- |
| `runtime/execution_affinity.py` | Identidades inmutables de release e instalación; documento canónico, huella y lectura estricta | Distinguir producto común, configuración de cliente y contratos de estado |
| `config/release_identity.py` | Verificación local de manifiesto, contenido de `src`, requisitos e inventario de versiones instaladas | Un nombre de release escrito a mano no demuestra los archivos ni el entorno observado |
| `config/procedure_configuration.py` | Conservación de bytes verificados, digest y snapshot completo, incluida compatibilidad | Fijar los datos realmente cargados y evitar verificarlos para luego leer otros bytes |
| Cuatro loaders de procedimientos | Separación de lectura de archivo y validación del documento | Reutilizar validadores actuales sobre los bytes ya verificados, sin una segunda lectura |
| Composición neutral y `workflow.py` | Validar correspondencia Foundry/procedimientos; fijar afinidad en ID del ejecutor inicial | MAF rechaza una release/configuración distinta antes de ejecutar handlers al restaurar |
| `ClassificationExecutor` | Guardar el documento de afinidad del host antes de llamar al agente | Hacer inspeccionable el contexto de versión; un atributo de alerta no lo selecciona |
| Composición productiva | Rechazar activación incompleta antes de proveedores | Mantener deshabilitada la ruta hasta disponer de selección previa al claim y admisión durable |

No se cambian SDK, modelos, prompts, publicaciones Foundry, parámetros operacionales,
autoridades READ/WRITE, tablas SQL, payloads de canal ni el formato del codec `1.0`.

## Identidad común y por instalación

`ProductReleaseIdentity` contiene `release_id`, `source_sha256` y
`environment_sha256`. `ExecutionAffinity` añade `installation_id`, huellas
Foundry/procedimientos, `execution-affinity-v1`, `incident-state-v1` y el formato
de checkpoint `1.0`. `incident-state-v1` es la primera etiqueta explícita del
contrato de aplicación en esta ruta; no es una versión del SDK o de Azure SQL.

La huella se calcula sobre JSON canónico. Los identificadores son exactos y
acotados; `latest`, `default`, hashes ambiguos, campos extra y versiones desconocidas
se rechazan. La lectura del documento no concede aprobación, consumo ni autoridad.
Una misma identidad de release se puede compartir entre instalaciones; sus
afinidades difieren si cambia la instalación o su configuración.

La identidad observada del código cubre los archivos del árbol de runtime y
`requirements-runtime.txt`, en orden de rutas estable y con bytes exactos. Se
excluyen cachés Python; entradas de runtime no admitidas, symlinks y tamaños
excesivos se rechazan. La observación del entorno incluye implementación y versión
de Python, sistema, arquitectura y todas las distribuciones instaladas con su
versión. Las identidades duplicadas se rechazan.

Consecuencias prácticas:

- Una modificación de código, configuración distribuida o versiones instaladas
  cambia la identidad; también puede hacerlo un checkout con bytes distintos.
- Un manifiesto construido con paquetes de desarrollo instalados describe ese
  entorno. El de producción debe construirse en el entorno final, no copiarse
  desde la máquina de desarrollo.
- Esta verificación no es el digest OCI, no verifica bytes de wheels o bibliotecas
  nativas y no acredita procedencia ni firma. El artefacto inmutable y su cadena
  de construcción siguen pendientes de entrega 4.
- Es una observación local. La instalación debe impedir modificaciones posteriores;
  no hay bloqueo del sistema de archivos ni revalidación continua del código cargado.
- La huella Foundry refleja configuración local, no un readback LIVE del proveedor.

El verificador recibe un manifiesto `product-release-v1` con exactamente
`schema_version`, `release_id`, `source_sha256` y `environment_sha256`. Sus claves
de entrada son `RUNTIME_RELEASE_MANIFEST`, `RUNTIME_RELEASE_SHA256` y
`RUNTIME_INSTALLATION_ID`; son obligatorias juntas. La ruta del paquete procede
del código instalado; sólo el consumidor explícito del verificador puede inyectar
otra para un ensayo. No hay descubrimiento desde variables de proceso implícitas.
**No configurar esas claves en el host todavía.** No se entrega una orden de
activación ni un manifiesto productivo inventado.

## Snapshot de procedimientos

El loader sigue aceptando el manifiesto de procedimientos `1.0` con catálogo,
gobierno y bindings. Lee y verifica cada archivo una vez y captura también los
bytes de compatibilidad incluidos en el producto. Los validadores reciben esos
documentos decodificados; no reabren archivos que podrían haber cambiado.

`manifest_sha256` conserva la referencia de entrada; `fingerprint` representa
el contenido de los cuatro documentos. Cambiar sólo la ubicación absoluta no
cambia la huella. Los objetos inyectados históricamente sin snapshot mantienen
`fingerprint=None` y no pueden entrar en la ruta de afinidad.

`workflow_options()` mantiene las instancias históricas. La ruta de afinidad usa
`verified_workflow_options()` para reconstruir admisión y bindings desde bytes
inmutables en cada grafo. Así, mutar el registro anterior no altera silenciosamente
una release ya identificada. Cambiar procedimientos requiere cargar otro snapshot
y obtener otra afinidad, no mutar un registro vivo.

## Comportamiento del workflow

La fábrica neutral admite `execution_affinity` únicamente junto con un snapshot
de procedimientos correspondiente y agentes con la misma huella Foundry. Se
comprueban de nuevo al construir el grafo. La ruta estricta rechaza overrides
separados de procedimientos, dominio o resolución de recursos sin versionar.
Los adaptadores restantes siguen siendo dependencias confiables del host; la
huella no convierte una inyección arbitraria en un proveedor verificado.

La clasificación usa el ID `classification-affinity-<huella>`. El SDK fijado crea
un checkpoint de entrada que ya incorpora la firma de ese grafo antes del primer
handler. Después, clasificación guarda el documento del host en shared state
antes de llamar al agente. No lo obtiene de `raw_attributes`, del canal o del LLM.
Un estado con otra afinidad se rechaza.

La restauración nativa con igual afinidad conserva la solicitud pendiente. Cambios
de release, código, entorno, instalación, Foundry o procedimientos modifican la
firma y se rechazan antes de handlers. No se reescriben firmas de históricos.
Pasar entre la ruta histórica y la nueva también es incompatible. Los workflows
sin afinidad conservan sus IDs y siguen leyendo los fixtures históricos existentes.

Este mecanismo **no asigna aún una identidad durable independiente de ejecución
antes de la admisión**, no selecciona trabajos de cola por release y no transforma
sesiones Foundry. El checkpoint de entrada liga la definición; no sustituye al
inventario de casos requerido para drenar ni al registro de identidad futura.

## Validación

Linux FULL NON-LIVE: **3.780 PASS, 24 excluidas y 3 avisos**, 74,37 s, Python 3.14.10.
Selección focal nueva: **77 PASS**. No se suma a la FULL. Los casos P7 se comparan
por identidad en el expediente externo del paquete. Windows y publicación de
P8-R1 permanecen pendientes hasta recibir y verificar sus evidencias.

Los nuevos casos cubren rechazo de código/entorno modificado, manifiestos inválidos,
aislamiento por instalación, snapshot inmune a cambios de archivos/registros,
compatibilidad incorporada al digest, restauración nativa, persistencia antes de
la primera llamada, codec actual, rechazo de overrides y consumo HITL monotónico.
El rechazo autorizado usado en la prueba no ejecuta una operación ni siquiera falsa.

La observación adicional sobre el árbol real confirmó que el inventario de código
y de distribuciones se puede calcular en este entorno. No acredita un contenedor
desplegado. SQL real, Foundry/MCP LIVE y despliegues no se han ejecutado.

## Siguiente paquete, dentro de P8

1. Persistir la asignación de ejecución/afinidad y su correlación con solicitud,
   checkpoint y continuación, sin adoptar históricos por inferencia.
2. Filtrar y reclamar atómicamente por afinidad en SQLite y Azure SQL; aplicar
   el mismo ámbito al recuperador P6/P7. El worker ajeno debe dejar contador,
   propietario, aprobación y estado intactos.
3. Añadir diagnóstico durable de incompatibilidad y admisión/drenaje coordinados.
   Un inventario HITL vacío por sí solo no demuestra que no haya WAIT o trabajo
   pendiente. Resolver la carrera del último conteo antes de activar N+1.
4. Cualificar datos históricos, carreras SQL, rollback y rutas de sesión pertinentes.
   El plazo de drenaje detiene una actualización; no decide una aprobación.
5. Con esos contratos integrados y probados, retirar el bloqueo de activación
   mediante un cambio explícito. No quitarlo sólo para poder arrancar con variables.

Decisión de MVP conservada: N termina sus casos y después se activa N+1.
Coexistencia de consumidores N/N+1, migración automática, factoría/CI y actualizaciones
por cliente aún no están acreditadas. Entregas 4–8 y fases F27–F48 conservan sus IDs
y pendientes. F27 LIVE permanece pausada.

## Referencias

- [Contrato de composición neutral](e3-core-recovery.md).
- [Configuración F46](f46-customer-configuration.md).
- [Checkpoint MAF](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints),
  contrastado el 17/11/2026 durante la revisión anterior. Para R1, comportamiento
  probado con core 1.13.0 instalado, sin actualizar dependencias.
- [Roadmap](roadmap-f27-f48.md).
