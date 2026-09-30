# Plan de evaluación — comunicación v1 (F24.3C)

## Estado y límites
Paquete LOCAL, no publicado en Foundry ni incorporado al catálogo productivo.
Criterios: communication-review-v1. Corpus: communication_review_v1.dev.jsonl.
24 casos sintéticos: 8 pass, 12 fail y 4 inconclusive como expectativas propuestas.
No son resultados de un modelo, ni etiquetas validadas por una persona.
Todas las etiquetas llevan assistant_proposed_unreviewed. Validar estructura,
referencias y cobertura no equivale a validar la corrección semántica del corpus.
Los siete archivos Python/tests certificados en F24.3B no cambian.

## Uso del corpus
Cada línea contiene un caso independiente. `expectation` es anotación exclusiva
del evaluador de pruebas; no se envía al Reviewer. `criterion_outcomes` etiqueta
solo los criterios enumerados. Los omitidos están SIN ETIQUETAR, no son pass.
Las filas positivas sí enumeran los siete pass. Las filas negativas y ambiguas
son casos focales: pueden requerir más etiquetas tras revisión humana.
`expectation.verdict` es una hipótesis de resultado del caso, no la salida de
ReviewAssessment. No se debe rellenar el resto de findings con pass y declarar
que el modelo ha sido evaluado. Las pruebas locales no llaman a ningún modelo.

Para una futura llamada se construirá ReviewRequest únicamente con context y
candidate, más review_id y versiones controlados por Python. ReviewAgentAdapter
producirá el sobre request/request_sha256. Nunca añadir expectation, family,
case_id de dataset, origin o label_status como instrucciones o pistas al juez.
La rúbrica está incorporada en system.instructions.md, no requiere abrir archivos
ni herramientas durante una revisión. El identificador agent-reviewer-sbx es una
convención local propuesta, no evidencia de que exista ese agente en Foundry.

## Antes de medir calidad cognitiva
1. Revisión humana de etiquetas, incluyendo los casos ambiguos y la separación
   entre contradicción, ausencia de respaldo e incertidumbre; registrar cambios
   con versión y resolver desacuerdos. No inventar revisor ni firma humana.
2. Preparar un HOLDOUT independiente, revisado y no utilizado para escribir la
   rúbrica. Mantener variantes de una misma familia en un único split. Este
   paquete solo contiene development; no se reclama un test ciego.
3. Certificar el runner real, modelo/deployment, versión, instrucciones exactas,
   herramientas AUSENTES, sesiones y reintentos del SDK antes de invocarlo.
4. Autorizar explícitamente número de llamadas, datos, presupuesto y cualquier
   alta de agente/evaluador. No reanudar incidents consumidos para generar datos.
5. Versionar corpus, rúbrica, prompt y código; fijar parámetros antes de mirar
   resultados. No afinar con holdout ni ocultar errores/no-respuestas.

## Métricas a registrar, no valores conseguidos
- Validez de respuesta, correlación, cobertura de criterios y referencias.
- Matriz pass/fail/inconclusive contra etiquetas humanas; no confundir errors
  o timeouts con inconclusive emitido por el modelo: registrar error separado.
- Falsos pass peligrosos y falsos rechazos, por criterio y por familia; publicar
  denominadores, abstenciones y desacuerdos, no solo exactitud promedio.
- Concordancia y estabilidad en repeticiones limitadas sobre datos estáticos.
- Latencia, tokens y coste observados; no fijar una cifra de coste sin medir.
La aceptación de producción y sus umbrales requieren decisión explícita antes
 de la prueba final. No se puede certificar un porcentaje con estas pruebas.

## Restricciones operacionales
No hay cambio de src, catálogo, destinatario, herramientas, permisos, dependencia,
red, Azure, Teams, SQL, MCP ni despliegue en esta microfase. PNA permanece cerrado.
REJECT-004 y REJECT-005 son históricos consumidos; no se reproducen. Un Reviewer
no puede crear autorización, saltarse HITL ni sustituir Procedure Validation.
Fallback e integración en la comunicación terminal quedan para F24.4 y no deben
ocultar ni reintentar decisiones humanas ya consumidas.

## Procedencia documental (consultada 28/09/2026)
El contrato del producto procede de F24.1, F24.2 y F24.3B. Las etiquetas de este
paquete las propone el asistente a partir de fixtures sintéticas; no son datos
extraídos de operaciones reales ni un benchmark de Microsoft.
- https://learn.microsoft.com/en-us/agent-framework/agents/evaluation
  Distingue evaluación local, de respuestas preexistentes y ejecución por queries.
- https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/custom-evaluators
  Custom evaluators sigue marcado preview; distingue checks de código y juicios
  por prompt. No se registra ni usa ese servicio en esta microfase.
No se copia su esquema de retorno (result/reason) sobre ReviewResult: este
paquete conserva el contrato de nuestro producto y no se anuncia compatible
con la API de evaluadores personalizados sin una adaptación explícita.
