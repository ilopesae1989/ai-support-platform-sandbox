# AI Support Platform — plan por fases y tareas

Corte documental OP54: **21/10/2026**. Proyecto «Creación de agentes». Contrato técnico: AI, AI-103 y agentes.

## Objetivo permanente

**F48 — PRODUCTIVE MVP CLOSED**: una plataforma real de soporte IT reutilizable, gobernada, segura, durable, auditable, mantenible, operable por otro equipo y desplegable por cliente.

El LLM interpreta y propone; Python gobierna identidad, procedimientos, parámetros, políticas, aprobación, despacho y aceptación; el humano autoriza cuando corresponde; MCP ejecuta; la evidencia acredita resultados. Teams es transporte y experiencia del operador. Tickets, conocimiento, sesiones y checkpoints no conceden autoridad operacional.

## Estado que debe retomarse

- F27.3 y F27-B02 continúan abiertos; subfase activa 2.7.
- 2.1–2.6 conservan sus cierres delimitados. 2.7-T01 y 2.7-T02 están verificadas en preparación y pruebas focales offline.
- R3 Windows: `OFFLINE_PROCESS_FOCAL_PASSED`; tres selecciones de 32, 1 y 8 casos. Los 14 SDK y 20 de guarda anteriores se conservan como ejecuciones históricas; no se suman como una FULL.
- Siguiente tarea de producto: **F27-B02-2.7-T03**, pendiente. Antes de proseguir se prepara el checkpoint Git solicitado para cambiar de chat.
- T03–T05, 2.8–2.10, G1–G6, B03–B11 y F28–F48 mantienen sus pendientes. Este checkpoint no certifica despliegue ni cierre global.

Los estados se apoyan en expedientes conservados fuera del repositorio. El README y este plan no contienen los informes crudos del entorno ni credenciales. La publicación Git queda acreditada por su salida y la coincidencia posterior del SHA remoto, no por la existencia de este texto.

## Método de seguimiento

Usar IDs estables y estados PENDIENTE, EN_CURSO, BLOQUEADO, HECHO_VERIFICADO o NO_APLICA_JUSTIFICADO. Cada actualización registra requisito, código/configuración, documentación oficial aplicable, evidencia, resultado y siguiente acción. Un criterio parcial no cierra su fase. El historial se conserva y los resultados anteriores no se reescriben.

Mantener un bloque principal activo. No añadir fases, B12, 2.11 ni gates para corregir un recolector. Las tareas nuevas F28-T01…F48-T05 son desglose de planificación solicitado ahora: sus decisiones técnicas se concretarán al activar la fase, sin anticipar proveedores ni activar operaciones.

## F27: bloques y aceptación

### F27-B01 — Reconciliar las pruebas con las interfaces publicadas. Cierre de ese alcance respaldado por los 87 focales y el push del commit 76fabdc. Mantén separada esta evidencia del cierre global de F27.

Estado: **HECHO_VERIFICADO**.

Criterio conservado: [x] F27-B01 — Reconciliar las pruebas con las interfaces publicadas. Cierre de ese alcance respaldado por los 87 focales y el push del commit 76fabdc. Mantén separada esta evidencia del cierre global de F27.

### F27-B02 — Fijar el perfil Foundry que ejecutará el READ gobernado.

Estado: **EN_CURSO**.

### F27-B03 — Instalar el procedimiento RG List en catálogo, bindings y gobierno

Estado: **PENDIENTE**.

Criterio conservado: el procedimiento RG List se admite por identidad, versión y configuración aprobadas, y cualquier configuración ausente o incompatible conserva el bloqueo correspondiente.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B03-T01** — Revisar procedure_catalog.v1.json, procedure_capability_bindings.v1.json y procedure_governance.py para materializar el caso usando los contratos existentes. Estado: PENDIENTE.
- [ ] **F27-B03-T02** — Definir el procedimiento y su versión. Estado: PENDIENTE.
- [ ] **F27-B03-T03** — Declarar sus condiciones de aplicación. Estado: PENDIENTE.
- [ ] **F27-B03-T04** — Vincular su paso a azure.resource_group.list. Estado: PENDIENTE.
- [ ] **F27-B03-T05** — Fijar la acción READ y sus parámetros autorizados. Estado: PENDIENTE.
- [ ] **F27-B03-T06** — Incorporar la metadata de gobierno necesaria para su admisión. Estado: PENDIENTE.
- [ ] **F27-B03-T07** — Aplicar la política HITL del proyecto. Estado: PENDIENTE.
- [ ] **F27-B03-T08** — Definir qué resultado acredita que el paso ha cumplido su objetivo. Estado: PENDIENTE.

### F27-B04 — Conectar esa configuración al consumidor productivo y a la entrada del escenario

Estado: **PENDIENTE**.

Criterio conservado: una entrada del escenario utiliza efectivamente el procedimiento, la capability y la versión Foundry configurados, tanto al comenzar como al continuar la ejecución.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B04-T01** — Concretar la entrada operativa del escenario F27 usando la normalización y el launcher existentes cuando corresponda; registrar el destino Teams autorizado. Estado: PENDIENTE.
- [ ] **F27-B04-T02** — Materializar una binding RG List válida en la configuración recibida por la raíz productiva. Estado: PENDIENTE.
- [ ] **F27-B04-T03** — Seguir esa configuración hasta la fábrica que inicia y restaura el workflow, verificando el mismo registro y selección en ambas operaciones. Estado: PENDIENTE.
- [ ] **F27-B04-T04** — Conectar y demostrar la entrada elegida, la fábrica configurada y el destino autorizado. El acuse del handler Teams actual no acredita el inicio de workflow. Estado: PENDIENTE.

### F27-B05 — Completar la producción y verificación de evidencia backend

Estado: **PENDIENTE**.

Criterio conservado: el verificador consume evidencia procedente de la ejecución y puede rechazar una evidencia ajena, manipulada, incompleta o repetida.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B05-T01** — Un sensor situado en la entrada real al handler group_list. Estado: PENDIENTE.
- [ ] **F27-B05-T02** — Exportación y recepción de sus eventos. Estado: PENDIENTE.
- [ ] **F27-B05-T03** — Procedencia verificable del productor. Estado: PENDIENTE.
- [ ] **F27-B05-T04** — Una implementación de confianza para verificar los recibos. Estado: PENDIENTE.
- [ ] **F27-B05-T05** — Correlación auténtica entre operación, aprobación humana, aprobación MCP, request backend y resultado. Estado: PENDIENTE.
- [ ] **F27-B05-T06** — Persistencia de la evidencia que permita aplicar el verificador. Estado: PENDIENTE.

### F27-B06 — Definir y probar la condición técnica que permite cerrar RG List

Estado: **PENDIENTE**.

Criterio conservado: la resolución del caso RG List depende de una condición verificable del procedimiento. Un juicio favorable del agente no basta para acreditar que la lectura requerida se realizó correctamente.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B06-T01** — Revisar el riesgo estático technical_success=False/None frente a una validación cognitiva satisfied y delimitar la condición técnica del procedimiento RG List, preservando el contrato de rutas anteriores. Estado: PENDIENTE.
- [ ] **F27-B06-T02** — Definir qué evidencia acredita su resultado. Estado: PENDIENTE.
- [ ] **F27-B06-T03** — Comprobar su relación con la operación autorizada. Estado: PENDIENTE.
- [ ] **F27-B06-T04** — Probar resultado técnico fallido, desconocido, incompleto o contradictorio. Estado: PENDIENTE.
- [ ] **F27-B06-T05** — Comprobar el caso en que el agente propone satisfied pese a esa evidencia. Estado: PENDIENTE.
- [ ] **F27-B06-T06** — Hacer que Python aplique la salida declarada por el procedimiento cuando no se cumple su condición de aceptación. Estado: PENDIENTE.

### F27-B07 — Obtener una validación NON-LIVE completa del conjunto final

Estado: **PENDIENTE**.

Criterio conservado: una validación completa y trazable del código que se pretende utilizar después.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B07-T01** — Cerrar los cambios necesarios y fijar commit/árbol, entorno, selección, exclusiones y alcance de una sola FULL NON-LIVE final conforme a la autorización concreta que corresponda. Estado: PENDIENTE.
- [ ] **F27-B07-T02** — Selección productiva del perfil RG List. Estado: PENDIENTE.
- [ ] **F27-B07-T03** — Admisión y gobierno del procedimiento instalado. Estado: PENDIENTE.
- [ ] **F27-B07-T04** — Rechazo de combinaciones incorrectas de versión, binding, herramienta o argumentos. Estado: PENDIENTE.
- [ ] **F27-B07-T05** — Resultado fallido o desconocido frente a validación cognitiva favorable. Estado: PENDIENTE.
- [ ] **F27-B07-T06** — Correlación y repetición. Estado: PENDIENTE.
- [ ] **F27-B07-T07** — Compatibilidad de las rutas existentes afectadas. Estado: PENDIENTE.
- [ ] **F27-B07-T08** — Ejecutar esa única FULL dentro de su alcance, conservar resultados nativos y clasificar fallos o interrupciones sin inventar recuentos ni autorizar un retry por inferencia. Estado: PENDIENTE.
- [ ] **F27-B07-T09** — Documentar el resultado completo y trazable del conjunto que se pretende usar; los 87 focales y las FULL históricas conservan su alcance original. Estado: PENDIENTE.

### F27-B08 — Acreditar el artefacto ejecutado y las identidades efectivas — G1 y G2

Estado: **PENDIENTE**.

Criterio conservado: la evidencia identifica los artefactos y actores efectivos de la ejecución, con los permisos correspondientes.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B08-T01** — Relacionar el código validado, el build, la imagen/digest y la versión del servidor MCP con la revisión que atiende efectivamente el ensayo — G1. Estado: PENDIENTE.
- [ ] **F27-B08-T02** — Revisar por separado la configuración de revisión y la configuración efectiva de aplicación; un digest escrito en IaC no es evidencia de la revisión servida. Estado: PENDIENTE.
- [ ] **F27-B08-T03** — Identificar la identidad autenticada y los permisos efectivos en Foundry→MCP — primera parte de G2. Estado: PENDIENTE.
- [ ] **F27-B08-T04** — Identificar la identidad y los permisos efectivos utilizados en MCP→Azure — segunda parte de G2. Estado: PENDIENTE.
- [ ] **F27-B08-T05** — Conservar el expediente de artefactos y actores efectivos vinculado a la operación concreta y a sus evidencias. Estado: PENDIENTE.

### F27-B09 — Demostrar el sensor, la correlación y la ausencia de ejecución previa — G3, G4 y G5

Estado: **PENDIENTE**.

Criterio conservado: el verificador puede emitir una conclusión sustentada sobre el intervalo pendiente. Si falta confianza o cobertura, la evidencia queda sin certificar.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B09-T01** — Preparar la calibración positiva autorizada del sensor en el mismo handler group_list que se pretende observar y verificar su procedencia — G3. Estado: PENDIENTE.
- [ ] **F27-B09-T02** — Demostrar la correlación verificable operación/aprobaciones/request backend y el rechazo de sustitución o repetición — G4. Estado: PENDIENTE.
- [ ] **F27-B09-T03** — Preparar la cobertura de todas las réplicas, el intervalo, el tratamiento de pérdidas y el mecanismo de cierre/watermark — capacidad previa de G5. Estado: PENDIENTE.
- [ ] **F27-B09-T04** — Obtener y cerrar la evidencia del intervalo efectivamente observado; sólo entonces evaluar ausencia de dispatch durante PENDING — conclusión posterior de G5. Estado: PENDIENTE.
- [ ] **F27-B09-T05** — Conservar la conclusión del verificador y dejar sin certificar cualquier intervalo con confianza, calibración o cobertura insuficientes. Estado: PENDIENTE.

### F27-B10 — Completar el E2E gobernado — G6

Estado: **PENDIENTE**.

Criterio conservado: el caso termina con estado persistido, evidencia correlacionada y comunicación recibida en el destino autorizado.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B10-T01** — Preparar el recorrido integrado: entrada, catálogo/gobierno, HITL, PreCall, agente fijado, MCP, resultado/evidencia, persistencia, transición y Teams. Estado: PENDIENTE.
- [ ] **F27-B10-T02** — Acreditar el escenario de aprobación pendiente y ausencia de ejecución durante el intervalo cubierto. Estado: PENDIENTE.
- [ ] **F27-B10-T03** — Acreditar el rechazo humano y la ausencia de operación no autorizada. Estado: PENDIENTE.
- [ ] **F27-B10-T04** — Acreditar autorización exacta válida, ejecución correspondiente, resultado verificable y salida correcta. Estado: PENDIENTE.
- [ ] **F27-B10-T05** — Acreditar bloqueo de identidad, herramienta o argumentos incorrectos en la frontera correspondiente. Estado: PENDIENTE.
- [ ] **F27-B10-T06** — Acreditar estado y comunicación correctos frente a fallo técnico o timeout. Estado: PENDIENTE.
- [ ] **F27-B10-T07** — Acreditar que replay o recuperación preservan la autoridad consumida e impiden repetición indebida. Estado: PENDIENTE.
- [ ] **F27-B10-T08** — Acreditar rechazo de certificación ante evidencia o sensor incompletos. Estado: PENDIENTE.
- [ ] **F27-B10-T09** — Observar recepción real de la comunicación en el destino Teams autorizado y relacionarla con estado persistido y evidencia correlacionada. Estado: PENDIENTE.

### F27-B11 — Cerrar F27.3 y realizar después la auditoría global de F27

Estado: **PENDIENTE**.

Criterio conservado: cierre documentado de F27.3 y, por separado, aceptación de la auditoría global F27, con referencias al código, configuración, pruebas y evidencia utilizados.

Tareas conservadas; su aceptación remite al criterio y dependencias del bloque:

- [ ] **F27-B11-T01** — Reconciliar primero los criterios y evidencias de F27.3 y documentar su cierre sólo cuando estén acreditados; mantener separada la posterior auditoría global F27. Estado: PENDIENTE.
- [ ] **F27-B11-T02** — Convivencia de VM Start y RG List. Estado: PENDIENTE.
- [ ] **F27-B11-T03** — Selección por configuración y bindings gobernados. Estado: PENDIENTE.
- [ ] **F27-B11-T04** — Identidad, acción y parámetros canónicos. Estado: PENDIENTE.
- [ ] **F27-B11-T05** — Política, HITL y PreCall aplicados. Estado: PENDIENTE.
- [ ] **F27-B11-T06** — Dispatch y consumo protegidos frente a repetición. Estado: PENDIENTE.
- [ ] **F27-B11-T07** — Conservación de resultado y evidencia. Estado: PENDIENTE.
- [ ] **F27-B11-T08** — Bloqueo cuando falta autoridad. Estado: PENDIENTE.
- [ ] **F27-B11-T09** — Extensión mediante componentes reutilizables. Estado: PENDIENTE.
- [ ] **F27-B11-T10** — Ausencia de duplicación del core o ramificaciones específicas por alerta. Estado: PENDIENTE.
- [ ] **F27-B11-T11** — Actualizar documentación del estado vigente, README y diferencias entre configuración deseada, desplegada y evidencia disponible. Estado: PENDIENTE.
- [ ] **F27-B11-T12** — Registrar por separado la aceptación de la auditoría global F27 y su checkpoint/publicación verificable. No iniciar F28 con F27.3 abierta. Estado: PENDIENTE.

## F27-B02: diez subfases y 54 tareas

### F27-B02-2.1 — Inventario actual y base reproducible

Estado: **HECHO_VERIFICADO**.

Dependencia original: Publicación de FASE 1 y relectura completadas; capturar ahora entorno Windows y definiciones actuales, sin inferencia.

Criterio de salida original: se conocen el entorno real y las definiciones revisadas; los desconocidos no se completan a partir de fixtures o recuerdos.

- [x] **F27-B02-2.1-T01** — Mantener el commit 76fabdc como base del trabajo. Registrar cualquier modificación posterior y su diff antes de usarla como nueva referencia. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.1-T02** — Obtener del entorno Windows que se utilizará el ejecutable Python, versión, entorno virtual y versiones efectivamente instaladas de agent-framework-core, agent-framework-foundry, agent-framework-openai, azure-ai-projects, openai y azure-identity. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.1-T03** — Revisar metadatos de configuración y referencias necesarias sin volcar secretos. Diferenciar settings declarados y valores efectivos del proceso previsto. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.1-T04** — Leer las definiciones actuales de los candidatos y las conexiones asociadas. Registrar proyecto, endpoint, nombre, versión devuelta por el servicio, modelo/despliegue, herramientas y política de aprobación, fecha y procedencia de la captura. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.1-T05** — Clasificar v13, v14 y probe v2 según el maestro y la nueva lectura. Mantener el pending histórico intacto: no aprobarlo, denegarlo, continuarlo, cancelarlo, eliminarlo ni reutilizar su sesión. Estado: HECHO_VERIFICADO.

### F27-B02-2.2 — Especificar el contrato cerrado del perfil READ

Estado: **HECHO_VERIFICADO**.

Dependencia original: Nombre y versión se fijan a partir del inventario; el contrato de autoridad puede prepararse offline.

Criterio de salida original: servidor, herramienta, política y argumentos tienen una correspondencia inequívoca; nombre y versión no se inventan.

- [x] **F27-B02-2.2-T01** — Formalizar estos campos en una única ficha que compare autoridad Python, perfil Foundry y configuración MCP. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.2-T02** — Revisar instrucciones y herramientas auxiliares del candidato para asegurar que no amplían este alcance. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.2-T03** — Conservar la distinción entre aprobación humana del procedimiento y aprobación técnica MCP. El runtime sandbox fuerza HITL humano también para READ aunque la capability tenga hitl_required=False. Estado: HECHO_VERIFICADO.

### F27-B02-2.3 — Resolver conexión, endpoint e identidades

Estado: **HECHO_VERIFICADO**.

Dependencia original: Relacionar candidato y contrato con la conexión/destino efectivo; G1 y G2 no se satisfacen sólo con IaC.

Criterio de salida original: no hay ambigüedad de destino ni atribución de identidad basada únicamente en nombres o configuración deseada.

- [x] **F27-B02-2.3-T01** — Contrastar project_connection_id, target de la conexión, server_url y server_label del agente. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.3-T02** — Registrar y resolver toda discrepancia de endpoint. Microsoft documenta que, si la conexión y server_url difieren, se usa el endpoint de la conexión. [M2] Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.3-T03** — Separar autenticación de entrada Foundry→MCP de identidad de salida MCP→Azure; identificar sus evidencias efectivas, audiencias y permisos aplicables. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.3-T04** — Relacionar el endpoint con el artefacto, digest y revisión realmente servidos. La descripción Bicep y sus tests son referencias para comparar, no prueba de despliegue. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.3-T05** — Delimitar qué evidencia de G1 y G2 existe y cuál falta. Las aprobaciones, RBAC, allowlist y elicitation no se sustituyen entre sí. Estado: HECHO_VERIFICADO.

### F27-B02-2.4 — Verificar SDK, selección de versión y controles en transporte

Estado: **HECHO_VERIFICADO**.

Dependencia original: Versiones realmente instaladas y endpoint/API previstos; separar prueba offline de comprobación del servicio.

Criterio de salida original: el mecanismo de selección es explícito y verificable; los puntos que sólo puede acreditar el servicio quedan definidos para 2.8. Si el mecanismo no puede fijar o acreditar una versión, impide avanzar a una validación nativa del candidato.

- [x] **F27-B02-2.4-T01** — Reproducir la inspección sobre las versiones efectivamente instaladas en Windows; el entorno Linux analizado no sustituye esa evidencia. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T02** — Inspeccionar con el SDK real y un transporte controlado sin red la URL, el cuerpo y la selección de API que produciría la fábrica productiva. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T03** — Comprobar cómo queda fijada la versión elegida. Distinguir argumento del constructor, referencia incluida en la petición y selección acreditada por el servicio. Si la API devuelve agent_reference, incorporarlo a la posterior comparación; si no, definir una evidencia equivalente verificable. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T04** — Verificar que max_tool_calls=1 y parallel_tool_calls=False llegan al cuerpo correcto y revisar su alcance por solicitud. Una opción presente no garantiza por sí sola un máximo global a través de varias llamadas, una continuación o reintentos. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T05** — Contabilizar peticiones de inferencia, reintentos y dispatch de herramientas como magnitudes distintas. Fijar límites y tratamiento de timeouts de acuerdo con el runner que se vaya a revisar. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T06** — Comprobar la conversión nativa de mcp_approval_request, su identificación y la serialización de mcp_approval_response; verificar la misma sesión y las referencias de continuidad usadas por ese SDK. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.4-T07** — Si se confirma una incompatibilidad, preparar el cambio mínimo con su diff y validación focal. Toda decisión de cambiar preview o dependencias deberá sustentarse en esa incompatibilidad, no en copiar un ejemplo reciente de otra API. Estado: HECHO_VERIFICADO.

### F27-B02-2.5 — Seleccionar la versión candidata y verificar su definición publicada

Estado: **HECHO_VERIFICADO**.

Dependencia original: 2.1–2.4. Una publicación nueva es condicional; primero definición/diff y alcance concreto.

Criterio de salida original: existe una versión identificada cuyo contenido observado coincide con lo diseñado. Un nombre de fixture o una creación histórica no cumplen este criterio.

- [ ] **F27-B02-2.5-T01** — Elegir una versión existente únicamente si el inventario y la comprobación de selección acreditan el contrato completo. Estado: NO_APLICA_JUSTIFICADO.
- [x] **F27-B02-2.5-T02** — Si hace falta otra versión, preparar primero su definición exacta y el diff frente a la referencia elegida: modelo, instrucciones, herramientas, conexión y always. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.5-T03** — Toda publicación en Foundry será una acción futura con objeto y alcance concretos; este plan no la ejecuta ni la presume autorizada por los permisos históricos de NON-LIVE. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.5-T04** — Tras la publicación que corresponda, releer la versión por nombre y número devueltos por el servicio, normalizar la definición y conservar su hash y fecha. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.5-T05** — Comparar lo releído con la ficha 2.2 y la conexión 2.3. Revisar cualquier diferencia antes de construir evidencia con ese candidato. Estado: HECHO_VERIFICADO.

### F27-B02-2.6 — Materializar la binding y cerrar las pruebas focales del contrato

Estado: **HECHO_VERIFICADO**.

Dependencia original: Referencia exacta revisada del perfil; preservar autoridad y negativos antes del claim.

Criterio de salida original: el candidato se selecciona de forma explícita y los negativos fallan por la condición que anuncian. Quedan separados composición, selección y certificación remota.

- [x] **F27-B02-2.6-T01** — Construir la binding exacta para azure.resource_group.list y suministrarla mediante el mecanismo explícito de configuración/composición elegido, manteniendo una referencia trazable a la versión revisada. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.6-T02** — Verificar identidad y contenido del registro a través de las raíces de composición y demostrar su consumo por el executor del recorrido bajo prueba. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.6-T03** — Verificar que un registro explícito vacío, una capability sin binding o una binding inválida bloquean la ruta correspondiente antes de consumir el claim. Distinguirlo de recorridos inferiores históricos que admiten registry=None. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.6-T04** — Mantener o ampliar sólo las pruebas necesarias para errores reales del contrato: rol o versión incorrectos, require_approval distinto de always, herramienta/servidor/argumentos no autorizados, solicitudes múltiples y correlaciones nativas inválidas. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.6-T05** — Usar una prueba del SDK/transporte para los campos que los capturadores de constructor no demuestran. Los tests existentes de wiring y sesión continúan sirviendo en su alcance original. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.6-T06** — Identificar el punto de configuración que utilizará el consumidor desplegado; la demostración completa de su consumo en producción continúa vinculada a G6. Estado: HECHO_VERIFICADO.

### F27-B02-2.7 — Preparar la prueba PENDING y satisfacer sus requisitos previos

Estado: **EN_CURSO**.

Dependencia original: Candidato/target concretos, G1–G5 previos aplicables y autorización LIVE separada antes de agent.run. Preparación del sensor y cierre posterior del intervalo son distintos.

Criterio de salida original: los requisitos previos aplicables están acreditados, el alcance es ejecutable y la autorización concreta necesaria está resuelta antes del LIVE. Hasta entonces pueden avanzar las tareas offline; no se inicia la inferencia.

- [x] **F27-B02-2.7-T01** — Preparar un runner limitado a una nueva invocación inicial begin y a inspeccionar su respuesta. Debe finalizar antes de continue_azure_operations; handle completo no cumple ese alcance. Estado: HECHO_VERIFICADO.
- [x] **F27-B02-2.7-T02** — Fijar el perfil exacto, sus hashes, target autorizado, timeout, número de intentos permitido, salida y tratamiento de errores. Un timeout o una respuesta ambigua no autorizan una repetición automática. Estado: HECHO_VERIFICADO.
- [ ] **F27-B02-2.7-T03** — Crear identificadores nuevos y una sesión nueva. La operación histórica pendiente no forma parte de la prueba. Estado: PENDIENTE.
- [ ] **F27-B02-2.7-T04** — Especificar la evidencia de G1–G5 y comprobar los requisitos previos descritos en el maestro. La instrumentación necesita calibración y procedencia verificables antes de esa inferencia. Estado: PENDIENTE.
- [ ] **F27-B02-2.7-T05** — Preparar el expediente de la acción LIVE concreta para que cualquier autorización futura recaiga sobre un runner, perfil, destino y límites ya revisados. Estado: PENDIENTE.

### F27-B02-2.8 — Observar la aprobación MCP nativa del candidato

Estado: **PENDIENTE**.

Dependencia original: Salida de 2.7 acreditada. Sólo begin nuevo y observar; ninguna respuesta approve=True o approve=False ni handle completo.

Criterio de salida original: se acredita que esa versión solicitó la aprobación prevista. La conclusión adicional de ausencia de dispatch requiere su evidencia backend; PENDING o logs vacíos por sí solos no la acreditan.

- [ ] **F27-B02-2.8-T01** — Invocar el begin previsto con la selección exacta del perfil y el target fijado. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T02** — Registrar la petición efectiva y la evidencia de selección que devuelve el servicio. Compararlas con las verificaciones offline. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T03** — Comprobar exactamente una solicitud nativa esperada de aprobación; distinguir response.id del identificador del item mcp_approval_request. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T04** — Correlacionar el identificador del item con el identificador nativo y function_call.call_id exigidos por el contrato del repositorio. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T05** — Revisar server_label, nombre group_list y argumentos exactos contra la autoridad Python; conservar el resultado crudo y su proyección de forma trazable. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T06** — Finalizar en PENDING. Tanto enviar approve=True como enviar approve=False serían otra petición: no forman parte de esta prueba de observación. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T07** — Si faltan la aprobación o la selección efectiva, hay solicitudes múltiples, discrepancias, error o timeout, registrar el resultado como fallido o no certificado según la evidencia; no convertirlo en un PASS ni repetirlo implícitamente. Estado: PENDIENTE.
- [ ] **F27-B02-2.8-T08** — Cerrar la ventana de observación de backend y evaluar por separado el no-dispatch del intervalo según G3–G5. Estado: PENDIENTE.

### F27-B02-2.9 — Verificar la continuación y el alcance real de los límites

Estado: **PENDIENTE**.

Dependencia original: Evidencia compartida con el recorrido que alimentará G6. Preparar desde 2.8 sin exigir G6 cerrado; la continuación real tiene condiciones y autorización propias.

Criterio de salida original: cada afirmación queda respaldada por su evidencia correspondiente. Si la continuación real o sus límites todavía no se han comprobado, este subpunto permanece abierto. Se puede documentar el subresultado «perfil con pausa nativa verificada» sin declarar completa toda la fase 2.

- [ ] **F27-B02-2.9-T01** — Consolidar la prueba NON-LIVE de conversión y reanudación con el SDK instalado, la misma AgentSession, la misma invocación y los identificadores correctos. Estado: PENDIENTE.
- [ ] **F27-B02-2.9-T02** — Especificar qué falta demostrar con la continuación real gobernada: selección efectiva del mismo perfil, correlación de la aprobación, dispatch permitido, resultado y número efectivo de llamadas/reintentos. Estado: PENDIENTE.
- [ ] **F27-B02-2.9-T03** — Ejecutar esa comprobación real cuando exista el alcance correspondiente dentro de las pruebas gobernadas que aportarán evidencia a G6; necesita condiciones y autorización propias. No se reutiliza por conveniencia la sesión histórica protegida. Estado: PENDIENTE.
- [ ] **F27-B02-2.9-T04** — Comparar los límites enviados y su comportamiento en cada solicitud del recorrido. No asumir que max_tool_calls=1 de una solicitud limita automáticamente toda la operación. Estado: PENDIENTE.
- [ ] **F27-B02-2.9-T05** — Distinguir compatibilidad en la misma sesión de durabilidad tras reinicio: las referencias efímeras del wrapper no prueban recuperación de una pausa tras caída del proceso. Estado: PENDIENTE.

### F27-B02-2.10 — Cerrar el expediente y enlazar con F27.3 y F48

Estado: **PENDIENTE**.

Dependencia original: Registrar estado por criterio y consolidar evidencia disponible, incluyendo pendientes. La documentación de un subresultado no cierra automáticamente el bloque.

Criterio de salida original: se conoce exactamente qué está demostrado y qué queda pendiente; ninguna comprobación de wiring, pausa aislada o texto generado sustituye el E2E de F27.3.

- [ ] **F27-B02-2.10-T01** — Reconciliar en una tabla la versión publicada, su conexión y definición, la binding Python, la petición efectiva, la respuesta nativa, la evidencia backend y el entorno SDK. Estado: PENDIENTE.
- [ ] **F27-B02-2.10-T02** — Registrar hashes, fechas, resultados, pruebas ejecutadas y pendientes, sin sobrescribir la evidencia histórica ni atribuir un perfil sintético a producción. Estado: PENDIENTE.
- [ ] **F27-B02-2.10-T03** — Incorporar la documentación y los cambios revisados al checkpoint de Git que corresponda al cierre del trabajo. El commit actual sigue siendo la referencia hasta que haya otra publicación verificada. Estado: PENDIENTE.
- [ ] **F27-B02-2.10-T04** — Actualizar el estado del punto 2 por criterio. Si sólo está verificada la pausa, dejar explícita la continuación pendiente; si falta una versión efectiva o un gate, mantener la certificación abierta. Estado: PENDIENTE.
- [ ] **F27-B02-2.10-T05** — Consolidar la entrega del perfil y sus restricciones a G6, que puede haberse iniciado con la salida de 2.8. Mantener separados el procedimiento RG List gobernado, el consumidor desplegado, la evidencia de resultado técnico, persistencia/transición y presentación Teams que todavía necesiten demostración integral. Estado: PENDIENTE.

### Nueve criterios originales de aceptación de B02

Se conservan los nueve criterios A–I. Sus frases incluyen notas de estado del plan inicial; esas notas son históricas. El avance actual se describe en las subfases precedentes y se reconciliará por criterio en 2.10. Esta transcripción no revierte los cierres de 2.1–2.6 ni vuelve a declarar pendiente el inventario ya acreditado.

- **F27-B02-ACEP-A** — Literal original: Nombre, versión y definición publicados identificados y revisados: pendiente de inventario actual y selección.
- **F27-B02-ACEP-B** — Literal original: Conexión y destino efectivos, herramienta group_list y always concordantes: pendiente de comprobación actual.
- **F27-B02-ACEP-C** — Literal original: Binding del proyecto concordante y consumida por la ruta prevista: contrato y propagación publicados; perfil productivo concreto pendiente.
- **F27-B02-ACEP-D** — Literal original: SDK real y mecanismo de selección efectiva verificados: lectura estática realizada; transporte del entorno Windows y confirmación del servicio pendientes.
- **F27-B02-ACEP-E** — Literal original: Solicitud MCP nativa para servidor/herramienta/argumentos esperados: antecedente probe v2 documentado; nueva certificación del candidato pendiente.
- **F27-B02-ACEP-F** — Literal original: Evidencia de ausencia de dispatch antes de aprobación: pendiente de los controles y del intervalo concreto; no se deduce del antecedente ni de fixtures HMAC.
- **F27-B02-ACEP-G** — Literal original: Pausa y continuación compatibles con las versiones usadas: soporte de contrato/fakes existente; comprobaciones focales de transporte y recorrido real pendientes según su alcance.
- **F27-B02-ACEP-H** — Literal original: Límites efectivos de cliente comprobados en el recorrido real: opciones presentes en código; verificación real pendiente, incluida la continuación que corresponda.
- **F27-B02-ACEP-I** — Literal original: Documentación y checkpoint finales coherentes: plan preparado; expediente de ejecución y cierre pendientes.

### Alcances y dependencias que siguen abiertos

- Los cierres 2.1–2.5 conservan inventario, contrato, mapa de metadatos, SDK offline y definición versionada revisada. G1/G2 aún necesitan evidencia efectiva; 2.8 necesita selección del servicio.
- 2.6 acredita la configuración explícita y su consumo en las composiciones probadas. No instala el procedimiento RG List en catálogo ni suministra el perfil al contenedor desplegado.
- T02 acredita perfil, hashes, destino confirmado, límites y tratamiento de errores con supervisor focal Windows. Los cortes cubren el hijo propio; no demuestran cancelación remota, ausencia de dispatch, descendientes ni garantía de tiempo real.
- Antes del LIVE de 2.8, preparar y acreditar los requisitos aplicables de G1–G5 vinculados a B05/B08/B09. La preparación y calibración del sensor precede a la inferencia; el cierre del intervalo se evalúa después.
- 2.9 comparte evidencia con G6; no exigir G6 cerrado como prerrequisito circular de 2.9. La aprobación o denegación MCP son otra petición y no pertenecen al ensayo que sólo observa PENDING.
- Conservar la sesión PENDING histórica sin aprobar, denegar, continuar, cancelar, eliminar ni reutilizar. No repetir presupuestos o autorizaciones históricas consumidas.
- El cierre de F27.3 y la auditoría global F27 son hitos separados. Mantener coexistencia y reutilización de VM Start y RG List; no imponer una tercera capability.

## F28–F48: tareas de planificación por fase

Se conservan los contratos de fase originales. Se añaden cinco tareas por fase: revisión del repo y fuentes vigentes, contrato/diseño, implementación necesaria, validación y aceptación documentada. Todas están PENDIENTE; sus criterios de seguimiento desarrollan el contrato y no crean gates de producto adicionales. No se programan aquí ejecuciones ni fechas de entrega.

Referencia transversal **dependencias_roadmap**:

Dependencias: F26 antes de F27; capabilities y gobierno antes del E2E; F30/F31 antes de afirmar autoridad durable; F32 no impone una tecnología por defecto; F36/F37 separan observabilidad y auditoría; F38/F39 cubren resiliencia y adversarial; F41 demuestra la ruta productiva; F43 la promoción; F44 la aceptación; F45 la operación; F46 la arquitectura reusable; F47 la factoría; F48 el cierre. NO saltar directamente a F41 ni comenzar F28 con F27.3 abierta.

### F28 — Multi-Source Ingestion: Azure Monitor/New Relic/SCOM vía adapters, normalized operational event

Estado: **PENDIENTE**.

**F28 — Multi-Source Ingestion.** Adapters de fuentes operacionales y un core neutral respecto del proveedor. Azure Monitor, New Relic, SCOM, ITSM y Outlook/Graph son candidatos del roadmap, no integraciones ya hechas. En su discovery se decidirá si mantener NormalizedAlert, generalizar a evento operacional o introducir una jerarquía compatible. Cierre: añadir una fuente sin modificar la lógica cognitiva u operacional central.

#### F28-T01 — Revisar fuentes y contrato de entrada

Estado: PENDIENTE.
Propósito: Inventariar adapters existentes y necesidades de Azure Monitor, New Relic, SCOM, ITSM y Outlook/Graph como candidatos.
Entregable: Matriz fuente → contrato vigente → adapter existente → carencia.
Criterio de seguimiento: Separar integraciones existentes de candidatas y comprobar la documentación oficial aplicable al iniciar F28.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F28-T02 — Decidir el contrato normalizado compatible

Estado: PENDIENTE.
Propósito: Resolver si se mantiene NormalizedAlert, se generaliza a evento operacional o se incorpora una jerarquía compatible.
Entregable: Decisión de contrato con mapeos, identidad, correlación y compatibilidad.
Criterio de seguimiento: La decisión conserva separación entre datos de la fuente y autoridad operacional.
Dependencias: F28-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F28-T01 y concretar este entregable con el estado observado.

#### F28-T03 — Implementar el alcance de adapters acordado

Estado: PENDIENTE.
Propósito: Añadir o ajustar sólo los adapters elegidos a partir de la revisión y registrar su composición.
Entregable: Diff de adapters, configuración y registros necesarios.
Criterio de seguimiento: La fuente acordada se integra por su frontera sin duplicar la lógica cognitiva u operacional central.
Dependencias: F28-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F28-T02 y concretar este entregable con el estado observado.

#### F28-T04 — Validar normalización e independencia del core

Estado: PENDIENTE.
Propósito: Comprobar ejemplos representativos, datos incompletos y entradas inválidas de las fuentes elegidas.
Entregable: Pruebas y evidencia por adapter y contrato.
Criterio de seguimiento: Añadir una fuente del alcance aceptado no requiere modificar la lógica central y conserva su correlación.
Dependencias: F28-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F28-T03 y concretar este entregable con el estado observado.

#### F28-T05 — Documentar y aceptar la incorporación

Estado: PENDIENTE.
Propósito: Consolidar configuración, compatibilidad, límites y evidencia del alcance real.
Entregable: Contrato de entrada y guía de incorporación de fuentes actualizados.
Criterio de seguimiento: Se satisface el cierre original de F28; las fuentes aún no integradas se identifican sin certificarlas.
Dependencias: F28-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F28-T04 y concretar este entregable con el estado observado.


### F29 — Real ITSM: vendor-neutral tickets, lookup, correlation, transitions, sin ticket como permiso

Estado: **PENDIENTE**.

**F29 — Real ITSM.** Integración real con un core neutral respecto del proveedor: creación, consulta, correlación, comentarios, actualización, transiciones, resolución y enlaces a evidencia según el contrato que se delimite. Un ticket puede solicitar una acción, pero no concede capability, identidad ni permiso para saltarse HITL o PreCall.

#### F29-T01 — Revisar integración ITSM y API candidata

Estado: PENDIENTE.
Propósito: Distinguir agentes, adapters y mocks actuales de una integración real y revisar la API del proveedor elegido.
Entregable: Inventario de contratos, operaciones requeridas y capacidades del proveedor.
Criterio de seguimiento: Queda identificado el alcance real sin convertir los tickets en autoridad operacional.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F29-T02 — Delimitar el contrato neutral de tickets

Estado: PENDIENTE.
Propósito: Definir creación, consulta, correlación, comentarios, actualización, transiciones, resolución y enlaces según el alcance acordado.
Entregable: Contrato neutral y mapeo del ciclo de vida del ticket.
Criterio de seguimiento: Los estados ITSM se relacionan con el workflow sin conceder capability, identidad o permiso HITL/PreCall.
Dependencias: F29-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F29-T01 y concretar este entregable con el estado observado.

#### F29-T03 — Implementar adapter y composición ITSM

Estado: PENDIENTE.
Propósito: Conectar el proveedor seleccionado mediante el contrato y la configuración gobernados.
Entregable: Adapter, configuración y tratamiento de errores revisados.
Criterio de seguimiento: Las operaciones implementadas corresponden al contrato delimitado y preservan la neutralidad del core.
Dependencias: F29-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F29-T02 y concretar este entregable con el estado observado.

#### F29-T04 — Validar la integración real y sus fallos

Estado: PENDIENTE.
Propósito: Comprobar las operaciones acordadas, correlación, transiciones y fallos con evidencia del alcance real.
Entregable: Resultados por operación, evidencia y casos de autoridad ausente.
Criterio de seguimiento: Un ticket no permite saltarse HITL o PreCall; resultados parciales no se presentan como resolución.
Dependencias: F29-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F29-T03 y concretar este entregable con el estado observado.

#### F29-T05 — Documentar y aceptar el servicio ITSM

Estado: PENDIENTE.
Propósito: Registrar el mapeo definitivo, límites, recuperación y evidencia de aceptación.
Entregable: Guía de integración y acta de alcance verificado.
Criterio de seguimiento: El contrato original F29 está acreditado para el proveedor y operaciones aceptados.
Dependencias: F29-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F29-T04 y concretar este entregable con el estado observado.


### F30 — Productive Workflow Durability: checkpoints WAIT/HITL, crash/restart recovery sin duplicación de authority

Estado: **PENDIENTE**.

**F30 — Productive Workflow Durability.** Checkpoints, reanudación, WAIT prolongado, HITL prolongado, crash/restart recovery, huérfanos y timeouts. Revalidar las APIs de Agent Framework antes de diseñar. Un checkpoint no concede permiso de replay: aprobación consumida, dispatch, idempotencia, rechecks y correlación conservan sus propias autoridades. Cierre: sobrevivir a retrasos y reinicios sin duplicar una operación o su autorización. Mantener el riesgo documentado de SessionStore experimental.

#### F30-T01 — Revisar durabilidad y APIs de Agent Framework

Estado: PENDIENTE.
Propósito: Leer las APIs vigentes y el código de checkpoints, sesiones, WAIT/HITL y reanudación.
Entregable: Mapa de estado durable, límites actuales y riesgo SessionStore experimental.
Criterio de seguimiento: Distinguir sesión, checkpoint, aprobación consumida, dispatch y autoridad de replay.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F30-T02 — Definir la recuperación gobernada

Estado: PENDIENTE.
Propósito: Establecer estados y condiciones de reanudación, timeouts y tratamiento de huérfanos.
Entregable: Contrato de recuperación con rechecks, idempotencia y correlación.
Criterio de seguimiento: Un checkpoint no concede permiso para repetir una operación; se identifican dependencias con F31.
Dependencias: F30-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F30-T01 y concretar este entregable con el estado observado.

#### F30-T03 — Implementar la persistencia y reanudación necesarias

Estado: PENDIENTE.
Propósito: Aplicar el diseño acordado a las fronteras del workflow sin duplicar autoridad.
Entregable: Diff de checkpoints y recuperación, ligado a su estado persistido.
Criterio de seguimiento: WAIT/HITL y reinicio utilizan el contrato de recuperación y no la memoria previa como autoridad.
Dependencias: F30-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F30-T02 y concretar este entregable con el estado observado.

#### F30-T04 — Validar retrasos, reinicios y fallos intermedios

Estado: PENDIENTE.
Propósito: Probar WAIT/HITL prolongado, crash/restart y recuperación de estados inciertos.
Entregable: Evidencia de reanudación y de ausencia de duplicación de operación o aprobación.
Criterio de seguimiento: Se demuestra la recuperación en el alcance acordado; F30/F31 deben estar acreditadas antes de afirmar autoridad durable completa.
Dependencias: F30-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F30-T03 y concretar este entregable con el estado observado.

#### F30-T05 — Documentar y aceptar la durabilidad

Estado: PENDIENTE.
Propósito: Consolidar runbook de recuperación, riesgos y evidencia de los límites.
Entregable: Guía de recuperación y matriz de aceptación F30.
Criterio de seguimiento: El cierre original de F30 está demostrado sin ocultar el alcance experimental de componentes usados.
Dependencias: F30-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F30-T04 y concretar este entregable con el estado observado.


### F31 — Operational State Store Hardening: Azure SQL, transacciones, concurrency, idempotencia, migrations, recovery

Estado: **PENDIENTE**.

**F31 — Operational State Store Hardening.** Persistencia autoritativa de workflows, aprobaciones, conversaciones, operaciones, locks, correlaciones e idempotencia. Azure SQL es el foco esperado; no introducir Cosmos por defecto. Evaluar transacciones, concurrencia, unicidad, transiciones monotónicas, índices, migraciones, retención, recuperación y consistencia. Cierre: la autoridad durable no depende de la memoria del proceso.

#### F31-T01 — Revisar el estado autoritativo y Azure SQL

Estado: PENDIENTE.
Propósito: Inventariar workflows, aprobaciones, operaciones, conversaciones, locks, correlación e idempotencia persistidos.
Entregable: Mapa de tablas, transacciones, invariantes y carencias.
Criterio de seguimiento: La revisión distingue persistencia autoritativa de caché y no impone Cosmos u otro almacén nuevo.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F31-T02 — Definir consistencia, concurrencia y recuperación

Estado: PENDIENTE.
Propósito: Decidir transacciones, unicidad, transiciones monotónicas, retención, índices y migraciones a partir de necesidades.
Entregable: Contrato de consistencia y plan de migración/recuperación.
Criterio de seguimiento: Las invariantes de autoridad e idempotencia sobreviven a concurrencia y reinicio.
Dependencias: F31-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F31-T01 y concretar este entregable con el estado observado.

#### F31-T03 — Implementar el refuerzo del almacén

Estado: PENDIENTE.
Propósito: Aplicar las modificaciones necesarias y su migración controlada.
Entregable: Diff de persistencia y artefactos de migración.
Criterio de seguimiento: Las escrituras y transiciones cumplen el contrato elegido sin depender de memoria de proceso.
Dependencias: F31-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F31-T02 y concretar este entregable con el estado observado.

#### F31-T04 — Validar transacciones, carreras y recuperación

Estado: PENDIENTE.
Propósito: Comprobar concurrencia, duplicados, fallos intermedios, migración y recuperación.
Entregable: Evidencia por invariante y escenario de fallo.
Criterio de seguimiento: Se preserva autoridad durable con F30 y se identifican explícitamente los escenarios no cubiertos.
Dependencias: F31-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F31-T03 y concretar este entregable con el estado observado.

#### F31-T05 — Documentar y aceptar el almacén

Estado: PENDIENTE.
Propósito: Registrar versión de esquema, mantenimiento, retención y procedimiento de recuperación.
Entregable: Guía operacional del estado autoritativo.
Criterio de seguimiento: El cierre original de F31 demuestra que la autoridad durable no depende de memoria local.
Dependencias: F31-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F31-T04 y concretar este entregable con el estado observado.


### F32 — Messaging & Idempotency: redelivery, DLQ, outbox según gap, efecto operacional no duplicado

Estado: **PENDIENTE**.

**F32 — Messaging & Idempotency.** Retry, DLQ, deduplicación, redelivery, mensajes venenosos, orden y correlación cuando exista una necesidad demostrada. No introducir Service Bus por estética. Con transporte at-least-once, evitar duplicación de efectos operacionales, aprobaciones y transiciones.

#### F32-T01 — Revisar las necesidades reales de mensajería

Estado: PENDIENTE.
Propósito: Identificar redelivery, orden, reintentos, mensajes venenosos y errores del transporte existente.
Entregable: Matriz de necesidades demostradas y comportamiento actual.
Criterio de seguimiento: No se introduce Service Bus, DLQ u outbox por defecto sin una carencia que lo justifique.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F32-T02 — Definir entrega e idempotencia

Estado: PENDIENTE.
Propósito: Precisar correlación, deduplicación y recuperación para el transporte elegido.
Entregable: Contrato de entrega, idempotencia y tratamiento de mensajes fallidos.
Criterio de seguimiento: Una entrega repetida no crea nueva autoridad ni duplica efectos operacionales.
Dependencias: F32-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F32-T01 y concretar este entregable con el estado observado.

#### F32-T03 — Implementar los mecanismos necesarios

Estado: PENDIENTE.
Propósito: Aplicar sólo los mecanismos de mensajería que resuelven el alcance acordado.
Entregable: Diff de transporte, persistencia y configuración justificada.
Criterio de seguimiento: La implementación conserva el contrato del workflow y la decisión tecnológica queda trazada.
Dependencias: F32-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F32-T02 y concretar este entregable con el estado observado.

#### F32-T04 — Validar duplicados y recuperación de mensajes

Estado: PENDIENTE.
Propósito: Comprobar redelivery, orden relevante, poison messages y recuperación según el diseño.
Entregable: Pruebas y evidencia de deduplicación y manejo de fallos.
Criterio de seguimiento: Los escenarios repetidos no duplican aprobaciones, transiciones ni operaciones.
Dependencias: F32-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F32-T03 y concretar este entregable con el estado observado.

#### F32-T05 — Documentar y aceptar la mensajería

Estado: PENDIENTE.
Propósito: Consolidar garantías, límites y runbook de recuperación del transporte.
Entregable: Contrato y guía de operación de mensajes.
Criterio de seguimiento: El cierre F32 acredita el alcance necesario sin exigir una tecnología no seleccionada.
Dependencias: F32-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F32-T04 y concretar este entregable con el estado observado.


### F33 — Identity/Secrets/Authorization Hardening: MI least privilege, tenant boundaries, RBAC, Entra, KeyVault

Estado: **PENDIENTE**.

**F33 — Identity / Secrets / Authorization Hardening.** Identidades administradas, mínimos privilegios, RBAC, Key Vault, roles de aplicación, grupos, workload identities, rotación, límites de tenants y segregación de clientes. Evitar una superidentidad compartida. Identidad de transporte, identidad operacional, autorización humana y autoridad de recurso son distintas. Una identidad comprometida no debe otorgar autoridad lateral innecesaria.

#### F33-T01 — Revisar identidades, secretos y permisos efectivos

Estado: PENDIENTE.
Propósito: Inventariar identidades de transporte, operación, recursos y aprobación humana, incluidos límites de tenant y cliente.
Entregable: Mapa de identidades, permisos, secretos y fronteras de confianza.
Criterio de seguimiento: La revisión distingue configuración declarada y permisos efectivos sin exponer secretos.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F33-T02 — Definir mínimos privilegios y segregación

Estado: PENDIENTE.
Propósito: Concretar RBAC, roles, grupos, workload identities, Key Vault y rotación donde apliquen.
Entregable: Matriz de autoridad y diseño de segregación/rotación.
Criterio de seguimiento: Se evita una superidentidad compartida y cada permiso tiene un propósito delimitado.
Dependencias: F33-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F33-T01 y concretar este entregable con el estado observado.

#### F33-T03 — Aplicar el refuerzo de identidad acordado

Estado: PENDIENTE.
Propósito: Configurar identidades y secretos mediante el mecanismo autorizado para cada ámbito.
Entregable: Cambios de configuración/infraestructura y evidencia de aplicación.
Criterio de seguimiento: Los cambios cumplen la matriz acordada y conservan aislamiento entre clientes.
Dependencias: F33-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F33-T02 y concretar este entregable con el estado observado.

#### F33-T04 — Validar acceso permitido y denegado

Estado: PENDIENTE.
Propósito: Comprobar privilegios necesarios, denegaciones, rotación y límites entre tenants/clientes.
Entregable: Evidencia positiva y negativa sin credenciales en los artefactos.
Criterio de seguimiento: Una identidad no obtiene autoridad lateral ajena al alcance aceptado.
Dependencias: F33-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F33-T03 y concretar este entregable con el estado observado.

#### F33-T05 — Documentar y aceptar el modelo de acceso

Estado: PENDIENTE.
Propósito: Registrar responsables, ciclo de vida, rotación, revocación y excepciones revisadas.
Entregable: Matriz final de acceso y runbook de identidad.
Criterio de seguimiento: El contrato F33 se acredita con evidencias efectivas y riesgos residuales explícitos.
Dependencias: F33-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F33-T04 y concretar este entregable con el estado observado.


### F34 — SharePoint / Knowledge Production: ACL trimming, freshness, provenance, cliente, no permiso por documento

Estado: **PENDIENTE**.

**F34 — SharePoint / Knowledge Production.** Conocimiento productivo gobernado con security trimming, ACL, frescura, proveniencia, versionado y aislamiento por cliente. La integración SharePoint y cualquier tecnología Foundry candidata se revisarán con información vigente al llegar. Un documento que dice «reiniciar la VM» no concede autoridad operacional.

#### F34-T01 — Revisar conocimiento y conectores candidatos

Estado: PENDIENTE.
Propósito: Revisar fuentes SharePoint, permisos y opciones vigentes de Foundry aplicables.
Entregable: Inventario de fuentes, ACL, versiones, frescura y opciones de integración.
Criterio de seguimiento: Los productos candidatos se evalúan con documentación vigente sin presumir adopción.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F34-T02 — Definir recuperación y gobierno del conocimiento

Estado: PENDIENTE.
Propósito: Establecer security trimming, procedencia, frescura, versionado y aislamiento.
Entregable: Contrato de recuperación y uso seguro del conocimiento.
Criterio de seguimiento: El texto recuperado no concede autoridad operacional ni elimina controles Python.
Dependencias: F34-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F34-T01 y concretar este entregable con el estado observado.

#### F34-T03 — Implementar conectores y controles necesarios

Estado: PENDIENTE.
Propósito: Integrar el conocimiento mediante las fronteras acordadas y la configuración por cliente.
Entregable: Diff/configuración de conectores y controles de acceso.
Criterio de seguimiento: La recuperación respeta la identidad y los permisos del alcance seleccionado.
Dependencias: F34-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F34-T02 y concretar este entregable con el estado observado.

#### F34-T04 — Validar permisos, frescura y procedencia

Estado: PENDIENTE.
Propósito: Comprobar documentos permitidos/denegados, cambios de ACL, datos obsoletos y contenido hostil.
Entregable: Evidencia por fuente y frontera de autorización.
Criterio de seguimiento: No hay acceso entre clientes ni transformación del documento en permiso operacional.
Dependencias: F34-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F34-T03 y concretar este entregable con el estado observado.

#### F34-T05 — Documentar y aceptar el conocimiento productivo

Estado: PENDIENTE.
Propósito: Consolidar fuentes, mantenimiento, limitaciones y recuperación ante fallos.
Entregable: Catálogo gobernado y guía de operación del conocimiento.
Criterio de seguimiento: F34 se cierra sólo para las fuentes y controles efectivamente acreditados.
Dependencias: F34-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F34-T04 y concretar este entregable con el estado observado.


### F35 — Confidence/Coverage/Fallback: confidence model y decisiones deterministas Python

Estado: **PENDIENTE**.

**F35 — Confidence / Coverage / Fallback.** Formalizar procedure_match, knowledge_coverage y confidence. Exact/partial/none son estados candidatos del contrato. El LLM puede evaluar semántica; Python gobierna la consecuencia: automatizar, preguntar, revisar o escalar. No usar umbrales arbitrarios sin evaluación.

#### F35-T01 — Revisar señales de confianza y cobertura

Estado: PENDIENTE.
Propósito: Inventariar procedure_match, knowledge_coverage, confidence y sus consumidores actuales.
Entregable: Mapa de señales, decisiones y evaluación disponible.
Criterio de seguimiento: Se distinguen confianza semántica, cobertura y autoridad operacional.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F35-T02 — Definir estados y consecuencias gobernadas

Estado: PENDIENTE.
Propósito: Decidir el contrato de exact/partial/none u otros estados justificados y sus consecuencias Python.
Entregable: Contrato de señales y tabla de decisiones.
Criterio de seguimiento: Los umbrales y decisiones tienen una evaluación prevista; no se adoptan valores arbitrarios.
Dependencias: F35-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F35-T01 y concretar este entregable con el estado observado.

#### F35-T03 — Implementar el contrato y las decisiones

Estado: PENDIENTE.
Propósito: Aplicar señales y validaciones deterministas en las fronteras previstas.
Entregable: Diff de contratos y decisiones de preguntar/revisar/escalar/automatizar.
Criterio de seguimiento: La salida LLM no puede conceder por sí sola permiso para ejecutar.
Dependencias: F35-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F35-T02 y concretar este entregable con el estado observado.

#### F35-T04 — Evaluar cobertura y alternativas

Estado: PENDIENTE.
Propósito: Medir el comportamiento con casos representativos, información incompleta y errores.
Entregable: Resultados de evaluación, umbrales justificados y límites.
Criterio de seguimiento: La evidencia sustenta las consecuencias adoptadas y expone insuficiencias de cobertura.
Dependencias: F35-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F35-T03 y concretar este entregable con el estado observado.

#### F35-T05 — Documentar y aceptar el comportamiento

Estado: PENDIENTE.
Propósito: Registrar métricas, decisiones y guía de revisión de umbrales.
Entregable: Contrato y matriz de aceptación de confianza/cobertura.
Criterio de seguimiento: El cierre F35 conserva Python como autoridad de la consecuencia operacional.
Dependencias: F35-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F35-T04 y concretar este entregable con el estado observado.


### F36 — Observability E2E: traces Agent Framework/Foundry/MCP/HITL/Teams, errors, latency, costs

Estado: **PENDIENTE**.

**F36 — Observability E2E.** Observar workflow, Agent Framework, Foundry, MCP, HITL, latencias, errores, reintentos, costes, entrega por canal, dependencias y correlación. El operador debe poder explicar qué ocurrió, dónde, cuándo, por qué, cuánto tardó, cuánto costó y qué falló. Observabilidad no equivale a autoridad de auditoría.

#### F36-T01 — Revisar observabilidad del recorrido completo

Estado: PENDIENTE.
Propósito: Mapear workflow, agentes, Foundry, MCP, HITL, dependencias y canales.
Entregable: Inventario de trazas/métricas y carencias de correlación.
Criterio de seguimiento: Se distinguen observaciones disponibles y evidencia de auditoría de F37.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F36-T02 — Definir el contrato de telemetría

Estado: PENDIENTE.
Propósito: Precisar eventos, correlaciones, errores, latencias, reintentos, coste y entrega por canal.
Entregable: Especificación de telemetría y consultas operacionales.
Criterio de seguimiento: El contrato permite explicar el recorrido sin registrar secretos ni conceder autoridad.
Dependencias: F36-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F36-T01 y concretar este entregable con el estado observado.

#### F36-T03 — Instrumentar las fronteras necesarias

Estado: PENDIENTE.
Propósito: Añadir la telemetría acordada y su configuración operacional.
Entregable: Diff/configuración de instrumentación, consultas y vistas.
Criterio de seguimiento: Cada punto se vincula al recorrido real y conserva sus límites de confianza.
Dependencias: F36-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F36-T02 y concretar este entregable con el estado observado.

#### F36-T04 — Validar observación y diagnóstico

Estado: PENDIENTE.
Propósito: Comprobar trazas en éxito y fallo, correlación, latencias, costes y entrega.
Entregable: Evidencia de consultas sobre escenarios representativos.
Criterio de seguimiento: El operador puede localizar qué ocurrió y qué falló con las limitaciones documentadas.
Dependencias: F36-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F36-T03 y concretar este entregable con el estado observado.

#### F36-T05 — Documentar y aceptar la observabilidad

Estado: PENDIENTE.
Propósito: Consolidar consultas, paneles, alertas y guía de diagnóstico.
Entregable: Guía operacional de observabilidad E2E.
Criterio de seguimiento: F36 se acepta sin equiparar telemetría a verificación de autoridad de F37.
Dependencias: F36-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F36-T04 y concretar este entregable con el estado observado.


### F37 — Audit & Evidence: cadena actor→autoridad→recurso→acción→resultado inmutable/correlacionado

Estado: **PENDIENTE**.

**F37 — Audit & Evidence.** Conservar la cadena evento → clasificación → procedimiento → gobierno → capability → identidad de recurso → policy → aprobación → operación/tool → respuesta → observación → validación → transición → comunicación → Evidence. Demostrar quién hizo qué, con qué autoridad, contra qué recurso y con qué resultado; evidencia legible por máquina cuando corresponda.

#### F37-T01 — Revisar la cadena de evidencia

Estado: PENDIENTE.
Propósito: Mapear desde evento y clasificación hasta autoridad, operación, validación, transición y comunicación.
Entregable: Matriz de productor, vínculo, verificador y custodia de cada evidencia.
Criterio de seguimiento: Se separa la observación de una afirmación operacional verificada.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F37-T02 — Definir integridad, correlación y conservación

Estado: PENDIENTE.
Propósito: Concretar el contrato de evidencia legible por máquina y sus fronteras de confianza.
Entregable: Contrato de evidencia, conservación y verificación.
Criterio de seguimiento: La cadena identifica actor, autoridad, recurso, acción y resultado con correlación verificable.
Dependencias: F37-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F37-T01 y concretar este entregable con el estado observado.

#### F37-T03 — Implementar productores y verificadores necesarios

Estado: PENDIENTE.
Propósito: Aplicar los componentes y registros que completen las carencias demostradas.
Entregable: Diff de producción, validación y persistencia de evidencia.
Criterio de seguimiento: Los consumidores validan el contrato y no aceptan texto LLM como prueba suficiente.
Dependencias: F37-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F37-T02 y concretar este entregable con el estado observado.

#### F37-T04 — Validar cadena e integridad de evidencia

Estado: PENDIENTE.
Propósito: Comprobar evidencias completas, ausentes, sustituidas, inconsistentes o repetidas.
Entregable: Resultados de verificación y casos negativos.
Criterio de seguimiento: Puede explicarse quién hizo qué y con qué autoridad; las insuficiencias no se promueven a éxito.
Dependencias: F37-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F37-T03 y concretar este entregable con el estado observado.

#### F37-T05 — Documentar y aceptar la auditoría

Estado: PENDIENTE.
Propósito: Consolidar custodia, consultas, retención y ejemplos verificables.
Entregable: Guía de auditoría y matriz de aceptación.
Criterio de seguimiento: El cierre F37 acredita la cadena requerida sin confundirla con observabilidad F36.
Dependencias: F37-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F37-T04 y concretar este entregable con el estado observado.


### F38 — Resiliency: fallos de proveedores y recovery fail-closed sin replays

Estado: **PENDIENTE**.

**F38 — Resiliency.** Fallos de Foundry, MCP, Teams, ITSM y SQL; timeout, red, degradación, reinicio de worker y fallo parcial. Recovery fail-closed, sin que un retry duplique autoridad ni eluda policy. Circuit breaker únicamente donde resulte útil.

#### F38-T01 — Revisar fallos de dependencias y recuperación

Estado: PENDIENTE.
Propósito: Inventariar comportamiento ante fallos Foundry, MCP, Teams, ITSM, SQL, red y procesos.
Entregable: Matriz de fallo, estado incierto y recuperación actual.
Criterio de seguimiento: Cada fallo se vincula a una frontera real y a la autoridad que debe preservarse.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F38-T02 — Definir política de resiliencia por frontera

Estado: PENDIENTE.
Propósito: Concretar timeout, degradación, recuperación y reintentos permitidos.
Entregable: Política de recuperación fail-closed por operación.
Criterio de seguimiento: El retry no duplica autoridad ni elude policy; circuit breaker sólo si aporta valor demostrado.
Dependencias: F38-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F38-T01 y concretar este entregable con el estado observado.

#### F38-T03 — Implementar las recuperaciones necesarias

Estado: PENDIENTE.
Propósito: Aplicar el comportamiento acordado en las fronteras identificadas.
Entregable: Diff de manejo de fallo y configuración.
Criterio de seguimiento: Cada recuperación conserva el estado y la correlación que justifican la siguiente transición.
Dependencias: F38-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F38-T02 y concretar este entregable con el estado observado.

#### F38-T04 — Validar fallos y recuperación parcial

Estado: PENDIENTE.
Propósito: Comprobar timeout, reinicio, fallos de red y respuestas ambiguas seleccionadas.
Entregable: Evidencia de estados finales y efectos preservados.
Criterio de seguimiento: La recuperación no duplica operaciones ni convierte incertidumbre en éxito.
Dependencias: F38-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F38-T03 y concretar este entregable con el estado observado.

#### F38-T05 — Documentar y aceptar la resiliencia

Estado: PENDIENTE.
Propósito: Registrar comportamiento esperado y acciones del operador por fallo.
Entregable: Runbook de fallos y matriz de cobertura.
Criterio de seguimiento: F38 se cierra con límites y riesgos residuales explícitos para el alcance real.
Dependencias: F38-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F38-T04 y concretar este entregable con el estado observado.


### F39 — Security Adversarial: inyección, target substitution, cross-customer, replay, evidence tampering

Estado: **PENDIENTE**.

**F39 — Security Adversarial.** Prompt injection directa/indirecta, tool injection, conocimiento hostil, sustitución de recursos, manipulación de target/payload, approval replay o stale approval, acceso entre clientes, escalada, suplantación de identidad/capability y manipulación de evidencia. Texto no confiable nunca se convierte directamente en autoridad.

#### F39-T01 — Revisar superficies y amenazas

Estado: PENDIENTE.
Propósito: Mapear entradas, herramientas, conocimiento, targets, aprobaciones, clientes y evidencia.
Entregable: Modelo de amenazas ligado al código/configuración actuales.
Criterio de seguimiento: Las amenazas se vinculan a fronteras concretas y no a una lista genérica sin alcance.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F39-T02 — Definir escenarios adversariales y expectativas

Estado: PENDIENTE.
Propósito: Delimitar inyección, suplantación, replay, aprobación obsoleta y manipulación de evidencia.
Entregable: Plan de escenarios y resultados deterministas esperados.
Criterio de seguimiento: Cada escenario comprueba que texto o datos hostiles no se convierten en autoridad.
Dependencias: F39-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F39-T01 y concretar este entregable con el estado observado.

#### F39-T03 — Corregir las carencias demostradas

Estado: PENDIENTE.
Propósito: Aplicar controles o correcciones derivados de amenazas y hallazgos reales.
Entregable: Diff de controles y registro de resolución de hallazgos.
Criterio de seguimiento: La solución conserva el contrato del producto y evita conceder autoridad lateral.
Dependencias: F39-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F39-T02 y concretar este entregable con el estado observado.

#### F39-T04 — Ejecutar y revisar la validación adversarial

Estado: PENDIENTE.
Propósito: Comprobar los escenarios seleccionados, incluidos límites entre clientes.
Entregable: Evidencia de ataques simulados, denegaciones y limitaciones.
Criterio de seguimiento: Los ataques no alteran recurso, capability, aprobación ni evidencia fuera de su autoridad.
Dependencias: F39-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F39-T03 y concretar este entregable con el estado observado.

#### F39-T05 — Documentar y aceptar el alcance de seguridad

Estado: PENDIENTE.
Propósito: Consolidar amenazas cubiertas, hallazgos y riesgos residuales.
Entregable: Matriz adversarial y decisión de aceptación del alcance.
Criterio de seguimiento: F39 queda acreditada por resultados concretos sin afirmar seguridad universal.
Dependencias: F39-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F39-T04 y concretar este entregable con el estado observado.


### F40 — Test Architecture: suites unit/contract/component/integration/offline/LIVE/recovery/performance

Estado: **PENDIENTE**.

**F40 — Test Architecture.** Separar unit, component, contract, integration, offline E2E, local container, LIVE, adversarial, migration, recovery y carga/rendimiento donde sea útil. Evitar tests monolíticos, dependencia cloud innecesaria y fixtures convertidos en autoridad del producto. Cada fallo debe identificar la frontera rota.

#### F40-T01 — Revisar arquitectura y cobertura de pruebas

Estado: PENDIENTE.
Propósito: Inventariar suites, dependencias cloud, fixtures y fronteras de validación.
Entregable: Mapa de suites → contrato → alcance de evidencia.
Criterio de seguimiento: Se distinguen unitarias, componentes, contratos, integración, offline y LIVE.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F40-T02 — Definir organización y selección de pruebas

Estado: PENDIENTE.
Propósito: Delimitar recuperación, migración, adversarial, contenedor y carga donde resulten útiles.
Entregable: Diseño de suites, selección, aislamiento y resultados.
Criterio de seguimiento: Cada fallo identifica una frontera y cada suite declara qué puede demostrar.
Dependencias: F40-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F40-T01 y concretar este entregable con el estado observado.

#### F40-T03 — Implementar la organización necesaria

Estado: PENDIENTE.
Propósito: Ajustar estructura y herramientas de prueba según las carencias verificadas.
Entregable: Diff de infraestructura y selección de pruebas.
Criterio de seguimiento: Los fixtures no pasan a ser autoridad del producto y no se añade cloud innecesaria.
Dependencias: F40-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F40-T02 y concretar este entregable con el estado observado.

#### F40-T04 — Validar suites y calidad de los fallos

Estado: PENDIENTE.
Propósito: Comprobar ejecución, aislamiento, negativos causales y clasificación de resultados.
Entregable: Evidencia de suites seleccionadas con su alcance.
Criterio de seguimiento: Las pruebas fallan por la condición que anuncian y no se suman ejecuciones para inventar una FULL.
Dependencias: F40-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F40-T03 y concretar este entregable con el estado observado.

#### F40-T05 — Documentar y aceptar la arquitectura de pruebas

Estado: PENDIENTE.
Propósito: Registrar cómo seleccionar, ejecutar e interpretar cada nivel de prueba.
Entregable: Guía de pruebas y matriz de cobertura.
Criterio de seguimiento: El cierre F40 hace trazable la relación entre evidencia y contrato sin exigir pruebas irrelevantes.
Dependencias: F40-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F40-T04 y concretar este entregable con el estado observado.


### F41 — Production E2E: success/reject/failure/no-authority con infra y durable state reales

Estado: **PENDIENTE**.

**F41 — Production E2E.** Ruta real con infraestructura, identidad, estado durable, HITL, operación, validación, comunicación y Evidence. Cubrir éxito, rechazo, fallo/fallback y ausencia de autoridad/fail-closed. VM Start aislado no basta.

#### F41-T01 — Revisar preparación de la ruta productiva

Estado: PENDIENTE.
Propósito: Identificar infraestructura, identidad, estado durable, contratos y evidencia de las fases previas.
Entregable: Matriz de requisitos y carencias del E2E productivo.
Criterio de seguimiento: Capabilities y gobierno están acreditados; no se salta directamente desde un caso aislado a F41.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F41-T02 — Definir escenarios y aceptación E2E

Estado: PENDIENTE.
Propósito: Precisar éxito, rechazo, fallo/alternativa y ausencia de autoridad para el alcance real.
Entregable: Expedientes de escenarios con destino, actores y límites.
Criterio de seguimiento: Cada escenario incluye HITL, operación, validación, comunicación y Evidence según corresponda.
Dependencias: F41-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F41-T01 y concretar este entregable con el estado observado.

#### F41-T03 — Completar la integración necesaria

Estado: PENDIENTE.
Propósito: Conectar las piezas productivas pendientes detectadas en la revisión.
Entregable: Diff/configuración y artefactos identificados del recorrido.
Criterio de seguimiento: La ruta utilizada coincide con el diseño revisado y su estado durable.
Dependencias: F41-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F41-T02 y concretar este entregable con el estado observado.

#### F41-T04 — Validar los escenarios productivos acordados

Estado: PENDIENTE.
Propósito: Ejecutar los expedientes en el entorno autorizado y comprobar el recorrido completo.
Entregable: Evidencia correlacionada de éxito, rechazo, fallo y ausencia de autoridad.
Criterio de seguimiento: VM Start aislado no sustituye la acreditación del alcance productivo completo.
Dependencias: F41-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F41-T03 y concretar este entregable con el estado observado.

#### F41-T05 — Documentar y aceptar el E2E

Estado: PENDIENTE.
Propósito: Consolidar artefactos ejecutados, resultados, límites y carencias restantes.
Entregable: Informe de aceptación E2E del alcance productivo.
Criterio de seguimiento: F41 se cierra únicamente con evidencia real suficiente del contrato original.
Dependencias: F41-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F41-T04 y concretar este entregable con el estado observado.


### F42 — Cost/Sandbox Optimization: eficiencia sin perder seguridad, trazabilidad ni durability

Estado: **PENDIENTE**.

**F42 — Cost & Sandbox Optimization.** Evaluar compute, Foundry/modelos, SQL, networking, logs/retención, ACR, Container Apps, recursos ociosos y entornos de prueba. No degradar seguridad, durabilidad u observabilidad por un ahorro pequeño. Distinguir optimización del sandbox de dimensionamiento productivo.

#### F42-T01 — Revisar consumo y recursos del entorno

Estado: PENDIENTE.
Propósito: Inventariar compute, modelos, SQL, red, logs, ACR, Container Apps y recursos ociosos.
Entregable: Línea base de consumo/coste y necesidades operativas.
Criterio de seguimiento: Se distingue sandbox de dimensionamiento productivo y no se presumen ahorros.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F42-T02 — Evaluar cambios y compromisos de optimización

Estado: PENDIENTE.
Propósito: Comparar opciones contra seguridad, durabilidad y observabilidad.
Entregable: Decisiones con ahorro esperado y efecto funcional/operacional.
Criterio de seguimiento: No se degrada el contrato del producto por un ahorro pequeño no justificado.
Dependencias: F42-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F42-T01 y concretar este entregable con el estado observado.

#### F42-T03 — Aplicar las optimizaciones seleccionadas

Estado: PENDIENTE.
Propósito: Modificar sólo configuración/recursos incluidos en el alcance acordado.
Entregable: Cambios trazables y referencia de coste anterior.
Criterio de seguimiento: La aplicación conserva los controles y la evidencia necesarios.
Dependencias: F42-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F42-T02 y concretar este entregable con el estado observado.

#### F42-T04 — Medir resultados e invariantes

Estado: PENDIENTE.
Propósito: Comparar consumo y funcionamiento después de los cambios.
Entregable: Medición de ahorro y comprobaciones de impacto.
Criterio de seguimiento: La evidencia muestra el efecto real y sus límites; no confunde previsión con medición.
Dependencias: F42-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F42-T03 y concretar este entregable con el estado observado.

#### F42-T05 — Documentar y aceptar el coste operativo

Estado: PENDIENTE.
Propósito: Registrar configuración, seguimiento y criterios de revisión futura.
Entregable: Guía de costes y decisiones sandbox/productivo.
Criterio de seguimiento: F42 conserva el contrato de seguridad, durabilidad y observabilidad del producto.
Dependencias: F42-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F42-T04 y concretar este entregable con el estado observado.


### F43 — CI/CD / IaC Promotion: artefacto inmutable, quality gates, IaC, migraciones, promoción controlada

Estado: **PENDIENTE**.

**F43 — CI/CD / IaC Promotion.** Source commit → tested artifact → imagen/paquete inmutable → promoción controlada. Pipelines, quality/security gates, IaC según autoridad real, migraciones, versionado, estrategia de rollback y evidencia de despliegue. El despliegue manual no es el modelo productivo final.

#### F43-T01 — Revisar build, entrega e infraestructura

Estado: PENDIENTE.
Propósito: Mapear commit, dependencias, artefactos, imágenes, IaC, migraciones y despliegues actuales.
Entregable: Inventario de cadena de entrega y autoridad real de despliegue.
Criterio de seguimiento: Se distinguen publicación Git, construcción de artefacto y despliegue.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F43-T02 — Definir promoción y reversión controladas

Estado: PENDIENTE.
Propósito: Concretar artefactos inmutables, quality/security gates, entornos y evidencia.
Entregable: Diseño de pipeline, promoción, migración y rollback.
Criterio de seguimiento: La promoción conserva la relación source → artefacto probado → destino.
Dependencias: F43-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F43-T01 y concretar este entregable con el estado observado.

#### F43-T03 — Implementar pipeline e IaC necesarios

Estado: PENDIENTE.
Propósito: Aplicar automatización e infraestructura según el diseño y la autoridad existente.
Entregable: Pipeline/IaC y configuración de promoción revisados.
Criterio de seguimiento: No se introduce un despliegue ajeno al alcance autorizado ni se depende del procedimiento manual como modelo final.
Dependencias: F43-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F43-T02 y concretar este entregable con el estado observado.

#### F43-T04 — Validar la cadena de promoción

Estado: PENDIENTE.
Propósito: Comprobar controles, artefacto ejecutado, migración y reversión según los escenarios acordados.
Entregable: Evidencia de promociones y controles que las detienen.
Criterio de seguimiento: El artefacto desplegado corresponde al probado y los fallos no eluden los controles.
Dependencias: F43-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F43-T03 y concretar este entregable con el estado observado.

#### F43-T05 — Documentar y aceptar la entrega

Estado: PENDIENTE.
Propósito: Registrar versiones, responsabilidades y operación de los pipelines.
Entregable: Guía de entrega/promoción y matriz de aceptación.
Criterio de seguimiento: F43 acredita un proceso repetible y trazable conforme al contrato original.
Dependencias: F43-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F43-T04 y concretar este entregable con el estado observado.


### F44 — UAT: validación operador/cliente/UX/aprobaciones/comunicaciones/accesibilidad

Estado: **PENDIENTE**.

**F44 — UAT.** Validar comportamiento funcional, flujo humano, experiencia de aprobación, comunicación, escalado, auditabilidad, expectativas del operador, runbooks y tratamiento de errores. UAT no equivale a las pruebas técnicas, ni estas sustituyen la aceptación humana.

#### F44-T01 — Revisar necesidades de aceptación del operador

Estado: PENDIENTE.
Propósito: Identificar usuarios, casos, errores y expectativas del alcance entregado.
Entregable: Mapa de aceptación humana y escenarios de trabajo.
Criterio de seguimiento: Se distingue UAT de la validación técnica previa.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F44-T02 — Definir el plan y criterios UAT

Estado: PENDIENTE.
Propósito: Concretar flujos humanos, aprobaciones, comunicación, escalado y auditabilidad.
Entregable: Plan UAT con escenarios y criterios acordados.
Criterio de seguimiento: Los criterios representan las necesidades del operador y del cliente.
Dependencias: F44-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F44-T01 y concretar este entregable con el estado observado.

#### F44-T03 — Preparar escenarios y resolver carencias

Estado: PENDIENTE.
Propósito: Configurar el entorno y corregir bloqueos funcionales o de experiencia detectados.
Entregable: Entorno UAT preparado y cambios trazados.
Criterio de seguimiento: La preparación conserva las fronteras de autoridad y no anticipa aceptación.
Dependencias: F44-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F44-T02 y concretar este entregable con el estado observado.

#### F44-T04 — Realizar la aceptación con usuarios

Estado: PENDIENTE.
Propósito: Recoger resultados humanos de los escenarios acordados y tratar incidencias.
Entregable: Evidencia de sesiones UAT, incidencias y resolución.
Criterio de seguimiento: La aceptación humana está registrada y no se infiere de tests técnicos.
Dependencias: F44-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F44-T03 y concretar este entregable con el estado observado.

#### F44-T05 — Documentar y formalizar la aceptación

Estado: PENDIENTE.
Propósito: Consolidar alcance aceptado, condiciones y asuntos abiertos.
Entregable: Acta UAT y material de uso revisado.
Criterio de seguimiento: F44 sólo se cierra con aceptación humana del alcance acordado.
Dependencias: F44-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F44-T04 y concretar este entregable con el estado observado.


### F45 — Product Operation: runbooks, ownership, monitoring, DR, troubleshooting, cambios, soporte por otro equipo

Estado: **PENDIENTE**.

**F45 — Product Operation.** Otro equipo debe poder operar la plataforma de forma segura: runbooks, monitorización, alertas, soporte, incidentes/cambios, backup/recovery, ownership, escalado, diagnóstico, fallos conocidos, mantenimiento y ciclo de vida. Si la respuesta a «¿puede operarlo otro equipo?» es no, F45 sigue abierta.

#### F45-T01 — Revisar capacidad de operación por otro equipo

Estado: PENDIENTE.
Propósito: Evaluar monitorización, soporte, incidentes, cambios, recuperación y mantenimiento.
Entregable: Matriz de responsabilidades, carencias y fallos conocidos.
Criterio de seguimiento: Se identifica qué impide que otro equipo opere la plataforma de forma segura.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F45-T02 — Definir el modelo de operación

Estado: PENDIENTE.
Propósito: Acordar ownership, escalado, runbooks y ciclo de vida de componentes.
Entregable: Modelo de soporte y procedimientos operacionales.
Criterio de seguimiento: Cada situación relevante tiene responsable y procedimiento aplicable.
Dependencias: F45-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F45-T01 y concretar este entregable con el estado observado.

#### F45-T03 — Completar las herramientas y procedimientos

Estado: PENDIENTE.
Propósito: Preparar monitorización, runbooks y automatizaciones necesarias para la operación.
Entregable: Material y configuración operacional revisados.
Criterio de seguimiento: El equipo receptor puede acceder a los recursos y evidencias requeridos dentro de su autoridad.
Dependencias: F45-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F45-T02 y concretar este entregable con el estado observado.

#### F45-T04 — Validar operación y recuperación con el equipo

Estado: PENDIENTE.
Propósito: Comprobar diagnóstico, mantenimiento y recuperación mediante escenarios representativos.
Entregable: Evidencia de ejecución por el equipo receptor.
Criterio de seguimiento: Se demuestra que otro equipo puede operar la plataforma sin depender de conocimiento informal del autor.
Dependencias: F45-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F45-T03 y concretar este entregable con el estado observado.

#### F45-T05 — Documentar y aceptar el traspaso operativo

Estado: PENDIENTE.
Propósito: Formalizar responsabilidades, límites, soporte y material de mantenimiento.
Entregable: Acta de traspaso y paquete operacional.
Criterio de seguimiento: Si otro equipo no puede operarlo de forma segura, F45 permanece abierta.
Dependencias: F45-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F45-T04 y concretar este entregable con el estado observado.


### F46 — Production Architecture Per Client: core común + tenant/customer config, aislamiento, datos, identidades, redes

Estado: **PENDIENTE**.

**F46 — Production Architecture Per Client.** Core común + configuración específica del cliente: tenants, suscripciones, grupos de recursos, red, identidades, secretos, datos, conocimiento, procedimientos, capabilities, canales, políticas, observabilidad, aislamiento y residencia cuando corresponda. Un cliente nuevo no significa un producto nuevo ni un fork completo.

#### F46-T01 — Revisar variaciones y aislamiento por cliente

Estado: PENDIENTE.
Propósito: Inventariar configuración de tenant, recursos, identidad, datos, conocimiento, canales y políticas.
Entregable: Mapa core común → configuración de cliente → necesidades de aislamiento.
Criterio de seguimiento: Se identifican personalizaciones ordinarias sin asumir un fork por cliente.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F46-T02 — Definir arquitectura productiva por cliente

Estado: PENDIENTE.
Propósito: Decidir aislamiento, red, residencia cuando aplique y contratos de configuración.
Entregable: Arquitectura y esquema de configuración de cliente.
Criterio de seguimiento: El diseño conserva el core reusable y la segregación de autoridad y datos.
Dependencias: F46-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F46-T01 y concretar este entregable con el estado observado.

#### F46-T03 — Implementar parametrización y límites necesarios

Estado: PENDIENTE.
Propósito: Aplicar la configuración de cliente y las fronteras previstas.
Entregable: Diff de parametrización, registros y configuración.
Criterio de seguimiento: Un cliente nuevo no exige modificar el core para una personalización ordinaria.
Dependencias: F46-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F46-T02 y concretar este entregable con el estado observado.

#### F46-T04 — Validar reutilización y aislamiento

Estado: PENDIENTE.
Propósito: Comprobar configuraciones de cliente, límites de acceso y ausencia de interferencia.
Entregable: Evidencia de aislamiento y variación soportada.
Criterio de seguimiento: Los recursos, identidades, datos y políticas se asocian al cliente correcto.
Dependencias: F46-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F46-T03 y concretar este entregable con el estado observado.

#### F46-T05 — Documentar y aceptar la arquitectura reusable

Estado: PENDIENTE.
Propósito: Consolidar decisiones, requisitos y límites de configuración.
Entregable: Guía de arquitectura y configuración por cliente.
Criterio de seguimiento: F46 demuestra core común y configuración específica sin producto/fork separado por cliente.
Dependencias: F46-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F46-T04 y concretar este entregable con el estado observado.


### F47 — Deployment Factory Per Client: factoría repetible provisioning/config/apps/knowledge/canales/monitoring

Estado: **PENDIENTE**.

**F47 — Deployment Factory Per Client.** La configuración de cliente produce infraestructura, identidades, aplicación, configuración, procedimientos, plugins, capabilities, conectores de conocimiento, canales, monitorización y políticas, con gates anteriores al despliegue. No copiar repositorios manualmente ni editar el core para una personalización ordinaria.

#### F47-T01 — Revisar entradas de la factoría

Estado: PENDIENTE.
Propósito: Revisar arquitectura F46, promoción F43 y contratos de configuración por cliente.
Entregable: Inventario de entradas, recursos producidos y carencias de automatización.
Criterio de seguimiento: La configuración necesaria está identificada y no se sustituye por copia manual de repositorios.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F47-T02 — Definir el contrato de despliegue repetible

Estado: PENDIENTE.
Propósito: Precisar validación de entradas, identidades, configuración, aplicaciones, conocimiento, canales y políticas.
Entregable: Contrato de factoría y controles anteriores al despliegue.
Criterio de seguimiento: Cada salida tiene origen trazable en configuración de cliente y artefacto versionado.
Dependencias: F47-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F47-T01 y concretar este entregable con el estado observado.

#### F47-T03 — Implementar la factoría acordada

Estado: PENDIENTE.
Propósito: Automatizar aprovisionamiento y configuración necesarios sobre los mecanismos elegidos.
Entregable: Artefactos de factoría y configuración de cliente.
Criterio de seguimiento: La personalización ordinaria se realiza mediante configuración y conserva el core.
Dependencias: F47-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F47-T02 y concretar este entregable con el estado observado.

#### F47-T04 — Validar despliegue y repetibilidad

Estado: PENDIENTE.
Propósito: Comprobar escenarios de configuración válida, inválida y recuperación definidos.
Entregable: Evidencia de producción de recursos/configuración y sus controles.
Criterio de seguimiento: El despliegue es reproducible y se detiene ante configuración que incumple el contrato.
Dependencias: F47-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F47-T03 y concretar este entregable con el estado observado.

#### F47-T05 — Documentar y aceptar la factoría

Estado: PENDIENTE.
Propósito: Consolidar incorporación de clientes, operación y mantenimiento de despliegues.
Entregable: Guía de factoría y evidencia de aceptación.
Criterio de seguimiento: F47 acredita despliegue por cliente sin copia manual del repositorio ni edición ordinaria del core.
Dependencias: F47-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F47-T04 y concretar este entregable con el estado observado.


### F48 — PRODUCTIVE MVP CLOSED: producto REAL reusable, auditable, secure, durable, mantenible, operable y desplegable por cliente

Estado: **PENDIENTE**.

**F48 — PRODUCTIVE MVP CLOSED.** Plataforma REAL reusable, gobernada, segura, durable, auditable, mantenible, operable y desplegable por cliente. No significa «demo end-to-end». Solo se cierra con evidencia suficiente de los contratos anteriores y del alcance aceptado.

#### F48-T01 — Revisar el alcance final y la evidencia acumulada

Estado: PENDIENTE.
Propósito: Conciliar contratos F27–F47, cierres, riesgos y alcance aceptado del producto.
Entregable: Matriz integral requisito → código/configuración → evidencia → estado.
Criterio de seguimiento: Los cierres históricos conservan su alcance y ninguna evidencia parcial se convierte en certificación global.
Dependencias: dependencias_roadmap; fase_activa_en_el_orden_conservado
Evidencia/commit: pendiente.
Siguiente acción: Realizar la revisión vigente del repo, contratos y documentación oficial al activar esta fase.

#### F48-T02 — Consolidar criterios finales de aceptación

Estado: PENDIENTE.
Propósito: Relacionar el alcance aceptado con reutilización, gobierno, seguridad, durabilidad, auditoría, mantenimiento, operación y despliegue por cliente.
Entregable: Matriz de aceptación final basada en los contratos existentes.
Criterio de seguimiento: No se añaden gates arbitrarios ni se elimina una obligación pendiente del contrato.
Dependencias: F48-T01
Evidencia/commit: pendiente.
Siguiente acción: Completar F48-T01 y concretar este entregable con el estado observado.

#### F48-T03 — Resolver las carencias finales identificadas

Estado: PENDIENTE.
Propósito: Remitir cada carencia demostrada a su fase y completar el trabajo necesario.
Entregable: Correcciones y evidencias enlazadas con los IDs de origen.
Criterio de seguimiento: Las carencias se cierran en su autoridad y alcance, sin eludir las fases pendientes.
Dependencias: F48-T02
Evidencia/commit: pendiente.
Siguiente acción: Completar F48-T02 y concretar este entregable con el estado observado.

#### F48-T04 — Verificar aceptación integral del producto

Estado: PENDIENTE.
Propósito: Revisar conjuntamente el recorrido real, operación y despliegue aceptados.
Entregable: Evaluación final de evidencia y aceptación del alcance.
Criterio de seguimiento: Hay evidencia suficiente de todos los contratos aplicables; una demo E2E no basta.
Dependencias: F48-T03
Evidencia/commit: pendiente.
Siguiente acción: Completar F48-T03 y concretar este entregable con el estado observado.

#### F48-T05 — Formalizar PRODUCTIVE MVP CLOSED

Estado: PENDIENTE.
Propósito: Cerrar el ledger y entregar la plataforma con responsabilidades y documentación completas.
Entregable: Registro final y paquete de producto operable.
Criterio de seguimiento: F48 sólo pasa a HECHO_VERIFICADO con aceptación explícita y evidencia suficiente del producto real definido.
Dependencias: F48-T04
Evidencia/commit: pendiente.
Siguiente acción: Completar F48-T04 y concretar este entregable con el estado observado.


## Contraste con documentación oficial

Consulta: 21/10/2026. La documentación del proveedor y las pruebas de la instalación tienen alcances distintos. Verificar nuevamente producto, lenguaje, API y versiones antes de cada decisión técnica; no migrar dependencias automáticamente por un ejemplo reciente.

- **MS01** — [Connect agents to Model Context Protocol servers](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol). Actualización visible: 2026-10-08. Conservar group_list y require_approval=always. El runner PENDING termina antes de enviar una respuesta de aprobación. R3 acredita el tratamiento de una respuesta sintética; 2.8 sigue pendiente.
- **MS02** — [Set up authentication for Model Context Protocol tools](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/mcp-authentication). Actualización visible: 2026-09-04. Mantener el mapa de conexión ya revisado y separar los saltos Foundry→MCP y MCP→Azure. Los metadatos y una prueba offline no certifican la identidad efectiva de G1/G2.
- **MS03** — [Agent identity concepts in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity). Actualización visible: 2026-08-25. Leer junto con MS04. No inferir que un agente con estado no publicado carece de identidad individual ni crear otra identidad por esa sola etiqueta.
- **MS04** — [Migrate from agent applications to the new agent endpoint and publishing experience](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/migrate-agent-applications). Actualización visible: 2026-07-21. Conservar agent-azure-operations-rg-list-sbx:1 ya creado y revisado. No repetir creación/publicación ni cambiar automáticamente API o endpoint por un ejemplo de otro modelo.
- **MS05** — [Create a model response — Microsoft Foundry API reference](https://ai.azure.com/api-reference/responses/create-response/). Actualización visible: no consignada en esta revisión. Relacionar esos campos con la petición serializada por el SDK instalado y la prueba offline. La selección efectiva del servicio y los límites a través de continuaciones conservan sus verificaciones de 2.8/2.9.
- **MS06** — [Azure MCP Server tools for Azure resource groups](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/resource-group). Actualización visible: 2026-09-25. Mantener la capability READ y el argumento gobernado de suscripción. La clasificación READ no sustituye la política HITL de la sandbox.
- **MS07** — [Using function tools with human in the loop approvals](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval). Actualización visible: 2026-10-15. Distinguir ese mecanismo de herramientas locales de la aprobación MCP nativa de Foundry. Mantener sesiones y correlación gobernadas; no reutilizar la sesión histórica pendiente ni introducir aprobación permanente.
- **MS08** — [Microsoft Agent Framework Workflows — Checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints). Actualización visible: 2026-09-16. La sesión SDK focal no demuestra recuperación productiva. Conservar F30/F31 y su revisión de API/almacén; la aparición de un proveedor en un ejemplo no decide migración a Cosmos ni sustituye el foco Azure SQL del contrato.

[M2]: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/mcp-authentication


## Recuento del corte

- F27: 11 bloques; B02: 10 subfases y 54 tareas, de las que 32 están HECHO_VERIFICADO, 1 NO_APLICA_JUSTIFICADO y 21 PENDIENTE.
- B03–B11: 64 tareas conservadas, pendientes.
- F28–F48: 105 tareas de planificación añadidas, todas pendientes.
- F17–F26 y F27.1/F27.2 conservan sus cierres históricos; este documento no los vuelve a ejecutar ni los sustituye.
