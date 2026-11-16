# Azure recreation snapshot

Configuración modular preservada del ensamblado local 09 del 15 de noviembre de
2026. Su publicación conserva el código de infraestructura; **la recreación en
Azure todavía no está acreditada**. No ejecutar `apply` sobre este snapshot sin
resolver las brechas de restauración y revisar un plan para el destino concreto.

## Contenido

| Módulo | Declaraciones de recursos |
| --- | ---: |
| access | 58 |
| app_services | 4 |
| bots | 1 |
| compute | 3 |
| container_apps | 7 |
| foundation | 7 |
| foundry | 20 |
| identities | 13 |
| integration | 3 |
| key_vault | 1 |
| messaging | 13 |
| network | 12 |
| observability | 6 |
| registry | 1 |
| search | 1 |
| sql | 10 |
| storage | 39 |
| **Total** | **199** |

El módulo Foundry incluye cuentas, proyectos, despliegues de modelos y
conexiones. **Las 74 versiones de agentes de 13 agentes están en el rescate
privado; sus definiciones no forman parte de estos recursos Terraform.** Será
necesario republicarlas mediante el procedimiento de restauración y conciliar
modelos, conexiones, identidades y herramientas. No se incluyen conversaciones.

Se conserva la separación existente entre el runtime de aplicación, MCP
operations, MCP READ y MCP WRITE. Esta publicación no fusiona los cuatro hosts.
El módulo histórico `legacy_poc` (26 declaraciones) no está llamado desde esta
raíz ni incluido aquí. Algunos planes y conectores históricos compartidos siguen
en el snapshot; su presencia no autoriza activar la POC.

## Entradas y material privado

Terraform está fijado en **1.9.6** y AzAPI en **2.9.0** para mantener la base del
ensamblado. Se incluye el lockfile existente con checksums para varias plataformas.
`recreation.tfvars.json.example` enumera las **33 entradas** con valor `null`:
es un inventario de campos a completar, no un archivo listo para desplegar.

- `subscription_id`, `tenant_id`: destino revisado.
- Doce variables `external_*`: identidades y referencias externas. Conciliar
  cada uso en el HCL con el catálogo privado del ensamblado; no adivinar valores
  ni reutilizar un object ID si la identidad ha sido recreada.
- Diez variables `secret_*`: credenciales de conexiones y listas de secretos
  de Container Apps. Los valores reales no se publican. `sensitive = true`
  oculta presentación, pero no cifra el estado ni permite subirlo a Git.
- Nueve entradas descriptivas adicionales: clave pública SSH, administrador SQL,
  correo de alertas, nombre de conexión Office 365, configuración de autorización
  Teams y client IDs de las aplicaciones MCP READ y operations/legacy.

Los nombres de recursos, endpoints, API versions y algunos IDs de topología
continúan reflejando el entorno exportado. Deben revisarse para el destino antes
de planificar. La parametrización para publicación no convierte el snapshot en
una plantilla genérica para cualquier suscripción.

`.gitignore` excluye estado, planes, valores reales, cachés, logs y backups. No
están incluidos los BACPAC, blobs, imágenes, backups de claves, credenciales de
Foundry, inventarios privados ni logs rescatados. Mantener esos archivos en sus
copias privadas y conservar sus manifiestos de integridad.

## Validación y límites conocidos

El ensamblado 09 fue validado localmente en Windows según el recibo aportado por
el operador. Para esta copia de publicación se verificaron el parseo de los 72
archivos HCL, el formato, las referencias de módulos/variables y la conservación
de las 199 declaraciones, con los cambios de valores a variables documentados
en `PUBLICATION_REVIEW.json`.

En el entorno de preparación de esta publicación, `init -backend=false` pudo
usar el proveedor local. La nueva ejecución de `validate` quedó bloqueada por
el entorno: el proceso proveedor no pudo crear su socket Unix (`operation not
permitted`). **No se declara una nueva validación nativa aprobada de esta copia.**
No se ejecutaron `plan`, `apply`, importaciones ni comandos de Azure.

Permanecen seis excepciones explícitas de validación de esquema AzAPI en
`module.foundry.azapi_resource.res-5`, `res-6`, `res-7`, `res-16`, `res-17` y
`res-18` (`schema_validation_enabled = false`). La validación sintáctica no
acredita que sus cuerpos sean aceptados por la API de creación.

Antes de restaurar hay que resolver y comprobar:

1. Semántica de creación de VM/discos y recursos que Azure genera como efecto
   de otros recursos; no confundir configuración exportada con contenido de disco.
2. Referencias de revisiones y tráfico de Container Apps, DNS y objetos generados
   por servicios; disponibilidad de las imágenes preservadas y acceso al registry.
3. Propiedades de lectura de las conexiones `Microsoft.Web`, autorización de
   conectores y credenciales que un GET no puede recuperar.
4. Identidades Entra, RBAC/ABAC, usuarios SQL y referencias entre módulos.
5. Proveedores registrados, cuotas y disponibilidad regional de modelos/SKUs.
6. Recuperación del Key Vault original si sigue en soft-delete; conservar las
   claves deshabilitadas hasta el paso autorizado correspondiente.
7. Importación y validación de SQL, Blob, Search y versiones de agentes por sus
   procedimientos de datos. El Terraform por sí solo no realiza esas restauraciones.

Para comprobar únicamente la configuración en un equipo con el proveedor
disponible, desde esta carpeta:

```powershell
terraform init -backend=false -input=false
terraform fmt -check -recursive
terraform validate
```

Estos comandos no sustituyen una prueba de recreación. F27 sigue pendiente de
integración desplegada, pruebas efectivas y acreditación; esta publicación no la cierra.

## Fuentes oficiales revisadas

- [Microsoft: funcionamiento y limitaciones de Azure Export for Terraform](https://learn.microsoft.com/en-us/azure/developer/terraform/azure-export-for-terraform/export-terraform-concepts)
- [HashiCorp: terraform validate y sus límites](https://developer.hashicorp.com/terraform/cli/commands/validate)
- [HashiCorp: archivo de bloqueo de dependencias](https://developer.hashicorp.com/terraform/language/files/dependency-lock)
- [HashiCorp: organización y exclusiones de archivos](https://developer.hashicorp.com/terraform/language/style)

Revisión de documentación: 16 de noviembre de 2026. Los contratos específicos
de las API se revisarán al preparar el plan de recreación, no se dan por certificados aquí.
