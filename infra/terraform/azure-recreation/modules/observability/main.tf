resource "azapi_resource" "res-1" {
  body = {
    properties = {
      eventHubAuthorizationRuleId = null
      eventHubName                = null
      logAnalyticsDestinationType = null
      logs = [{
        category      = "ContainerAppConsoleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "ContainerAppSystemLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "ContainerAppHTTPLogs"
        categoryGroup = null
        enabled       = true
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSpringAppConsoleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionConsoleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionPoolEventLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionLifeCycleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
      }]
      metrics = [{
        category = "AllMetrics"
        enabled  = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
      }]
      serviceBusRuleId = null
      storageAccountId = null
      workspaceId      = azapi_resource.res-6.id
    }
  }
  name      = "diag-f27-g4-http-obs03"
  parent_id = var.ref_container_apps_res_7_id
  type      = "microsoft.insights/diagnosticSettings@2021-05-01-preview"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      eventHubAuthorizationRuleId = null
      eventHubName                = null
      logAnalyticsDestinationType = null
      logs = [{
        category      = "ContainerAppConsoleLogs"
        categoryGroup = null
        enabled       = true
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "ContainerAppSystemLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "ContainerAppHTTPLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSpringAppConsoleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionConsoleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionPoolEventLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
        }, {
        category      = "AppEnvSessionLifeCycleLogs"
        categoryGroup = null
        enabled       = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
      }]
      metrics = [{
        category = "AllMetrics"
        enabled  = false
        retentionPolicy = {
          days    = 0
          enabled = false
        }
      }]
      serviceBusRuleId = null
      storageAccountId = null
      workspaceId      = azapi_resource.res-6.id
    }
  }
  name      = "f27-op74d-console-to-law"
  parent_id = var.ref_container_apps_res_7_id
  type      = "microsoft.insights/diagnosticSettings@2021-05-01-preview"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      armRoleReceivers           = []
      automationRunbookReceivers = []
      azureAppPushReceivers      = []
      azureFunctionReceivers     = []
      emailReceivers = [{
        emailAddress         = var.alerts_email_address
        name                 = "email-icenter-microsoft"
        useCommonAlertSchema = true
      }]
      enabled           = true
      eventHubReceivers = []
      groupShortName    = "ICenterOps"
      itsmReceivers     = []
      logicAppReceivers = []
      smsReceivers      = []
      voiceReceivers    = []
      webhookReceivers  = []
    }
  }
  location  = "global"
  name      = "ag-icenter-sandbox-ops"
  parent_id = var.ref_foundation_res_6_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "operations"
  }
  type = "microsoft.insights/actionGroups@2024-10-01-preview"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      armRoleReceivers = [{
        name                 = "Monitoring Contributor"
        roleId               = "749f88d5-cbae-40b8-bcfc-e573ddc772fa"
        useCommonAlertSchema = true
        }, {
        name                 = "Monitoring Reader"
        roleId               = "43d0d8ad-25c7-4714-9337-8ba259a9fe05"
        useCommonAlertSchema = true
      }]
      automationRunbookReceivers = []
      azureAppPushReceivers      = []
      azureFunctionReceivers     = []
      emailReceivers             = []
      enabled                    = true
      eventHubReceivers          = []
      groupShortName             = "SmartDetect"
      itsmReceivers              = []
      logicAppReceivers          = []
      smsReceivers               = []
      voiceReceivers             = []
      webhookReceivers           = []
    }
  }
  location  = "global"
  name      = "Application Insights Smart Detection"
  parent_id = var.ref_foundation_res_6_id
  type      = "microsoft.insights/actionGroups@2024-10-01-preview"
}
resource "azapi_resource" "res-5" {
  body = {
    etag = "\"2005ad85-0000-0200-0000-6ad7535c0000\""
    kind = "web"
    properties = {
      Application_Type                = "web"
      Flow_Type                       = "Bluefield"
      IngestionMode                   = "LogAnalytics"
      Request_Source                  = "rest"
      SamplingPercentage              = null
      WorkspaceResourceId             = azapi_resource.res-6.id
      publicNetworkAccessForIngestion = "Enabled"
      publicNetworkAccessForQuery     = "Enabled"
    }
  }
  location  = "northeurope"
  name      = "appi-icenter-sandbox-neu"
  parent_id = var.ref_foundation_res_6_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "operations"
  }
  type = "microsoft.insights/components@2020-02-02-preview"
}
resource "azapi_resource" "res-6" {
  body = {
    etag = "\"0a01f2eb-0000-0c00-0000-6a72f5f60000\""
    properties = {
      features = {
        enableLogAccessUsingOnlyResourcePermissions = true
        legacy                                      = 0
        searchVersion                               = 1
      }
      publicNetworkAccessForIngestion = "Enabled"
      publicNetworkAccessForQuery     = "Enabled"
      retentionInDays                 = 30
      sku = {
        name = "PerGB2018"
      }
      workspaceCapping = {
        dailyQuotaGb = 0.1
      }
    }
  }
  location  = "northeurope"
  name      = "log-icenter-sandbox-neu"
  parent_id = var.ref_foundation_res_6_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "operations"
  }
  type = "Microsoft.OperationalInsights/workspaces@2025-07-01"
}
