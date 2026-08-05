# AI Support Platform Sandbox

Sandbox técnica para desplegar y validar una plataforma multiagente de soporte basada en Microsoft Foundry y servicios Azure.

## Datos base

- Cliente: icenter
- Entorno: sandbox
- Región primaria: westeurope
- Presupuesto máximo mensual: 250 EUR
- Suscripción: Azure AI Sandbox – iCenter Microsoft
- Microsoft Foundry: Basic Agent Setup
- Interfaz principal: Microsoft Teams
- Repositorio documental: SharePoint Online
- ITSM inicial: ServiceNow
- Human in the loop: obligatorio para todas las operaciones de escritura

## Principios de diseño

- Sin alta disponibilidad.
- Sin red privada.
- Sin Private Endpoints.
- Sin Durable Task Scheduler.
- Durable Functions con Azure Storage.
- Azure AI Search Free condicionado a capacidad.
- Azure SQL Database Basic.
- Service Bus Standard.
- Container Apps Consumption con escala a cero.
- Un modelo de chat compartido.
- Un modelo de embeddings.
- Azure MCP Server oficial de Microsoft alojado en Azure Container Apps.
- Ningún agente tendrá Owner, Contributor ni User Access Administrator.

## Modelos candidatos aprobados

- Chat: gpt-5-mini
- Versión: 2025-08-07
- Deployment: DataZoneStandard
- Capacidad inicial: 10 K TPM

- Embeddings: text-embedding-3-small
- Versión: 1
- Deployment: DataZoneStandard
- Dimensiones: 768
- Capacidad inicial: 10 K TPM

## Estado actual

- Contexto Azure validado.
- Proveedores registrados.
- Región West Europe validada.
- Cuota de modelos validada.
- Azure AI Search Free estimado como viable con límites.
- Recursos Azure aún no desplegados.
