# F27-B05-T04 | Integración de confianza OFFLINE — expediente R1 + adenda R4

## Adenda R4 — reconciliación local gobernada (28/10/2026)

**Precedencia temporal:** este apartado documenta el estado posterior al texto
original R1, que se conserva a continuación sin borrar sus criterios ni su
carácter de propuesta histórica. La presencia de la adenda NO certifica que
se haya efectuado commit, push, despliegue, LIVE o cierre de B05-T04.

- **OBSERVADO_WINDOWS 28/10/2026 07:31:08 UTC:** siete rutas locales sin stage,
  cuatro modificadas con seguimiento y tres nuevas, sobre HEAD
  `b48353f241637781bb9bfbf59049d75f45aae24a` y TREE
  `3b811c7edd4dbe8c3c2c249e88f65dbfcd7280e9`.
  El paquete de exportación acredita 592 blobs del HEAD y siete versiones
  locales mediante hashes; no supone lectura semántica manual integral.
- **HISTÓRICO:** FULL NON-LIVE R2 `2821 passed, 24 deselected, 3 warnings`,
  exit code 0, siete hashes inalterados. Usó `cryptography 50.0.0` en el
  venv; 83 focales con `cryptography 50.0.2` ocurrieron separadamente en TEMP.
  Dry-run de dependencias 50.0.2 correcto; build OCI/CI todavía no acreditado.
- **Ámbito de las siete rutas:** `requirements-runtime.txt`,
  `requirements-dev.txt`, `tests/agents/test_foundry_rg_list_sdk_transport_offline.py`,
  `tests/test_application_container_image_contract.py`,
  `src/workflows/incident_resolution/mcp_receipt_trust.py`,
  `tests/workflows/incident_resolution/test_mcp_receipt_trust.py` y este documento.
- **Corrección R4 solo sobre las últimas tres rutas:** el parser convierte
  excepciones JSON extremas (`ValueError`/`RecursionError`) en rechazo contractual
  `UnsupportedEvidence`; procesa decimales JSON desde el token exacto con
  `Decimal` y únicamente admite valores integralmente representables dentro
  del rango I-JSON, sin permitir redondeos binarios silenciosos. Se añaden
  negativos y compatibilidad para `1.0`, `1e2` y `-0.0`.
- **Límite de compatibilidad:** `canonical_subject_v1` conserva el contrato
  para valores Python ya materializados (incluidos `float` integrales). Los
  consumidores de JSON bruto deben usar `parse_subject_json_v1` antes de
  verificar; un `float` redondeado por otro parser no permite reconstruir el
  valor JSON original. No se reivindica RFC 8785 completo.
- **Antireplay:** una firma ECDSA válida no constituye identidad de operación
  ni prueba de no-repetición; `proof_id` no sirve como única clave anti-replay.
  La cadena LIVE exige claves públicas confiadas fuera de la evidencia,
  firmantes independientes, correlación autenticada, almacenamiento duradero
  de replay, cobertura de réplicas, retención verificable y ventanas G4/G5.
- **Gobierno de cambios:** R4 requiere preflight HEAD/TREE/siete SHA exactos,
  autorización local limitada a tres rutas y postflight. El resultado de su
  aplicación y los nuevos tests deben acreditarse con recibos de Windows;
  la preparación de un parche o un PASS en entorno aislado no acredita el
  estado actual del equipo. COMMIT, PUSH y LIVE requieren autoridad separada.

---

### Texto original R1 conservado como histórico (antes de su aplicación)

# F27-B05-T04 | Propuesta de integración OFFLINE (sin despliegue)

**Estado:** CANDIDATO / REVIEW ONLY / no write aplicado al repositorio de producto.
**Base Git fijada:** `b48353f241637781bb9bfbf59049d75f45aae24a` (`phase16-wip`).

## Alcance mínimo del parche (5 archivos)

- Nuevo `src/workflows/incident_resolution/mcp_receipt_trust.py` con verificación ES256 por clave pública.
- Nuevo `tests/workflows/incident_resolution/test_mcp_receipt_trust.py` con pruebas adversariales e integración con `mcp_backend_evidence_contract`.
- Adición de la dependencia directa propuesta `cryptography==50.0.2` en `requirements-runtime.txt` y `requirements-dev.txt`.

**No se modifica** el contrato vigente, ni el flujo productivo, ni Foundry, MCP, Azure o la imagen OCI. El módulo no se importa automáticamente desde el consumidor ni configura una raíz de confianza LIVE.

## Contrato de recibo

Se conserva `source_receipt={issuer, proof_id}`.

`proof_id=es256:v1:<SHA256-SPKI-DER-HEX>:<ECDSA-P256-SHA256-P1363-RS-BASE64URL-NOPAD>`.

Los bytes a firmar (dominio V1, RFC8785 NO IMPLEMENTADO en su totalidad):

```
AI-SUPPORT-F27-B05-RECEIPT-V1\0 || scope || NUL || issuer || NUL || domain || NUL || kid || NUL || canonical_json_v1
```

`scope` es fijo, confiable, fuera de la evidencia (tenant/proyecto/entorno). `kid` procede exclusivamente del SPKI público registrado por una autoridad independiente. Las claves se fijan por emisor y por dominio permitido; no se pueden reutilizar entre emisores.

El perfil canónico V1 rechaza Unicode, claves duplicadas cuando el JSON pasa por el parser estricto, números no enteros y valores fuera de JSON/I-JSON. **No se declara RFC8785 pleno.**

## Separación de confianza y límites

1. Una firma del propio `mcp_backend` **NO es una auditoría independiente** de `attested_release=true`, del origen o de la ausencia de dispatch.
2. `coverage_sensor` debe contar con una raíz de confianza independiente del proceso MCP y del resto de productores, y calcular hechos observables de todas las réplicas, watermarks, ventanas de ingesta/exportación y fallos.
3. Los registros OP71 actuales no contienen `source_receipt` ni identificadores de operación Foundry: el verificador no transforma esos watermarks en recibos autenticados.
4. Se necesita una política separada para claves, rotación/revocación, emisión, almacenamiento de no-replay y correlación autenticada. No se debe derivar confianza de campos de un bundle recibido.
5. Ninguna firma, por sí sola, certifica una ausencia; el contrato exigente `verify_backend_evidence()` añade condiciones de cobertura y correlación.
6. Cualquier invocación Azure Key Vault, asignación de roles, despliegue de imagen o ejecución Foundry/MCP requiere una autorización LIVE/WRITE propia.

## Dependencia propuesta (pendiente de evaluación de resolución)

PyPI declara `cryptography==50.0.2` publicado el 30/09/2026, compatible con Python 3.14. Es una propuesta de pin **todavía no resuelta contra todos los paquetes del runtime del producto**, ni probada en su build de CI. El entorno local puede tener otra versión: no actualizarlo automáticamente. Ver: https://pypi.org/project/cryptography/50.0.2/.

## Criterios de aceptación antes de cualquier WRITE local

- Verificación actual de HEAD exacto y worktree limpio.
- Comprobación de que los destinos nuevos no existen; dependencias coinciden con blob Git esperado.
- `git apply --check` pasa con el parche; no se llama `git apply` sin autorización explícita.
- Tests dedicados y paquete completo del proyecto se ejecutarán tras el cambio con una decisión de autoridad separada.
- No declarar B05-T04 cerrado hasta verificación independiente con claves autorizadas y evidencias auténticas.

## Referencias

- GitHub `ilopesae1989/ai-support-platform-sandbox`, HEAD `b48353f2...`.
- Microsoft Learn: https://learn.microsoft.com/en-us/azure/key-vault/keys/about-keys-details
- Microsoft Learn: https://learn.microsoft.com/en-us/dotnet/api/azure.security.keyvault.keys.cryptography.cryptographyclient
- RFC 8785: https://www.rfc-editor.org/rfc/rfc8785.html
