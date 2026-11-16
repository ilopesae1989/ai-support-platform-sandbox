resource "azapi_resource" "res-1" {
  body = {
    properties = {
      api = {
        brandColor  = "#0078D4"
        description = "Microsoft Office 365 is a cloud-based service that is designed to help meet your organization's needs for robust security, reliability, and user productivity."
        displayName = "Office 365 Outlook"
        iconUri     = "https://static.powerapps.com/resource/ppcr/releases/v1.0.1831/1.0.1831.5113/office365/icon.png"
        id          = "/subscriptions/${var.subscription_id}/providers/Microsoft.Web/locations/northeurope/managedApis/office365"
        name        = "office365"
        type        = "Microsoft.Web/locations/managedApis"
      }
      changedTime              = "2026-11-10T12:11:03.1665898Z"
      createdTime              = "2026-08-13T07:07:21.5370689Z"
      customParameterValues    = {}
      displayName              = var.office365_connection_display_name
      nonSecretParameterValues = {}
      statuses = [{
        status = "Connected"
      }]
      testLinks = [{
        method     = "get"
        requestUri = "https://management.azure.com:443/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Web/connections/office365/extensions/proxy/testconnection?api-version=2016-06-01"
      }]
    }
  }
  location  = "northeurope"
  name      = "office365"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Web/connections@2016-06-01"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      api = {
        brandColor  = ""
        description = "Connect to Azure Service Bus to send and receive messages. You can perform actions such as send to queue, send to topic, receive from queue, receive from subscription, etc."
        displayName = "Service Bus"
        iconUri     = "https://static.powerapps.com/resource/ppcr/releases/v1.0.1816/1.0.1816.4885/servicebus/icon.png"
        id          = "/subscriptions/${var.subscription_id}/providers/Microsoft.Web/locations/northeurope/managedApis/servicebus"
        name        = "servicebus"
        type        = "Microsoft.Web/locations/managedApis"
      }
      changedTime           = "2026-08-13T07:18:17.2320473Z"
      createdTime           = "2026-08-13T07:18:17.2320473Z"
      customParameterValues = {}
      displayName           = "servicebus-2"
      statuses = [{
        status = "Connected"
      }]
      testLinks = []
    }
  }
  location  = "northeurope"
  name      = "servicebus-1"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Web/connections@2016-06-01"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      api = {
        brandColor  = "#ba141a"
        description = "Microsoft SQL Server is a relational database management system developed by Microsoft. Connect to SQL Server to manage data. You can perform various actions such as create, update, get, and delete on rows in a table."
        displayName = "SQL Server"
        iconUri     = "https://static.powerapps.com/resource/ppcr/releases/v1.0.1828/1.0.1828.4964/sql/icon.png"
        id          = "/subscriptions/${var.subscription_id}/providers/Microsoft.Web/locations/northeurope/managedApis/sql"
        name        = "sql"
        type        = "Microsoft.Web/locations/managedApis"
      }
      changedTime           = "2026-08-13T07:12:47.0652471Z"
      createdTime           = "2026-08-13T07:12:47.0652471Z"
      customParameterValues = {}
      displayName           = "Connection name: sql"
      statuses = [{
        status = "Connected"
      }]
      testLinks = [{
        method     = "get"
        requestUri = "https://management.azure.com:443/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Web/connections/sql/extensions/proxy/testconnection?api-version=2016-06-01"
      }]
    }
  }
  location  = "northeurope"
  name      = "sql"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Web/connections@2016-06-01"
}
