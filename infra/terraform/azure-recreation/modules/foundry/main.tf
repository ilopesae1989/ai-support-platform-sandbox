resource "azapi_resource" "res-1" {
  body = {
    kind = "AIServices"
    properties = {
      allowProjectManagement = true
      apiProperties = {
        qnaAzureSearchEndpointKey = null
      }
      associatedProjects  = ["ilopesae-3489"]
      customSubDomainName = "ilopesae-3489-resource"
      defaultProject      = "ilopesae-3489"
      disableLocalAuth    = false
      networkAcls = {
        defaultAction       = "Allow"
        ipRules             = []
        virtualNetworkRules = []
      }
      publicNetworkAccess = "Enabled"
    }
    sku = {
      name = "S0"
    }
  }
  location  = "swedencentral"
  name      = "ilopesae-3489-resource"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.CognitiveServices/accounts@2025-10-01-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {}
  }
  location  = "swedencentral"
  name      = "ilopesae-3489"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-3" {
  body = {
    kind = "AIServices"
    properties = {
      allowProjectManagement = true
      apiProperties = {
        qnaAzureSearchEndpointKey = null
      }
      associatedProjects  = ["aifproj-icenter-sbx"]
      customSubDomainName = "aif-icenter-sbx-eus2"
      defaultProject      = "aifproj-icenter-sbx"
      disableLocalAuth    = false
      networkAcls = {
        defaultAction       = "Allow"
        ipRules             = []
        virtualNetworkRules = []
      }
      publicNetworkAccess = "Enabled"
    }
    sku = {
      name = "S0"
    }
  }
  location  = "eastus2"
  name      = "aif-icenter-sbx-eus2"
  parent_id = var.ref_foundation_res_4_id
  type      = "Microsoft.CognitiveServices/accounts@2025-10-01-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "AppInsights"
      credentials   = var.secret_foundry_res_4_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        ApiType    = "Azure"
        ResourceId = "${var.ref_observability_res_5_id}"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "${var.ref_observability_res_5_id}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "appi-icenter-sandbox-neu-1893"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-5" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience      = "api://7f510755-760d-4b2f-a2ef-b45b9cd17a88"
      authType      = "ProjectManagedIdentity"
      category      = "RemoteTool"
      error         = null
      expiryTime    = null
      isDefault     = false
      isSharedToAll = false
      metadata = {
        toolEntityId = "azureml://location/eastus/apiCenter/registry-prod-bl/type/tools/objectId/azure-mcp-server/version/1"
        type         = "catalog_MCP"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_3_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-operations-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-6" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience                    = "api://930f18f1-5bac-4c6d-87de-80666eb36c9e"
      authType                    = "AgenticIdentityToken"
      category                    = "RemoteTool"
      error                       = null
      expiryTime                  = null
      isDefault                   = false
      isSharedToAll               = false
      metadata                    = {}
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_4_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-rglist-read-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-7" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience                    = "api://${var.external_89b57f13a066}"
      authType                    = "AgenticIdentityToken"
      category                    = "RemoteTool"
      error                       = null
      expiryTime                  = null
      isDefault                   = false
      isSharedToAll               = false
      metadata                    = {}
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_5_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-vmstart-write-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-8" {
  body = {
    properties = {
      authType      = "CustomKeys"
      category      = "RemoteTool"
      credentials   = var.secret_foundry_res_8_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        knowledgeBaseName = "kb-icenter-support-sbx"
        type              = "knowledgeBase_MCP"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://srch-icenter-sbx-swc.search.windows.net/knowledgebases/kb-icenter-support-sbx/mcp?api-version=2026-05-01-preview"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "kb-kb-icenter-support--d5seg"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "CognitiveSearch"
      credentials   = var.secret_foundry_res_9_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        ApiType              = "Azure"
        ApiVersion           = "2024-05-01-preview"
        DeploymentApiVersion = "2023-11-01"
        ResourceId           = "${var.ref_search_res_1_id}"
        displayName          = "srch-icenter-sbx-swc"
        type                 = "azure_ai_search"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://srch-icenter-sbx-swc.search.windows.net/"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "srchicentersbxswc0d5seg"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      currentCapacity = 2500
      deploymentState = "Running"
      model = {
        format  = "OpenAI"
        name    = "gpt-4.1-mini"
        version = "2025-04-14"
      }
      raiPolicyName        = "Microsoft.DefaultV2"
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
    sku = {
      capacity = 2500
      name     = "GlobalStandard"
    }
  }
  name      = "gpt-4.1-mini"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
}
resource "azapi_resource" "res-11" {
  body = {
    properties = {
      currentCapacity = 500
      deploymentState = "Running"
      model = {
        format  = "OpenAI"
        name    = "gpt-5"
        version = "2025-08-07"
      }
      raiPolicyName        = "Microsoft.DefaultV2"
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
    sku = {
      capacity = 500
      name     = "GlobalStandard"
    }
  }
  name      = "gpt-5"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
}
resource "azapi_resource" "res-12" {
  body = {
    properties = {
      currentCapacity = 35
      deploymentState = "Running"
      model = {
        format  = "OpenAI"
        name    = "gpt-5-mini"
        version = "2025-08-07"
      }
      raiPolicyName        = "Microsoft.DefaultV2"
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
    sku = {
      capacity = 35
      name     = "DataZoneStandard"
    }
  }
  name      = "gpt-5-mini-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
}
resource "azapi_resource" "res-13" {
  body = {
    properties = {
      currentCapacity = 10
      deploymentState = "Running"
      model = {
        format  = "OpenAI"
        name    = "text-embedding-3-small"
        version = "1"
      }
      raiPolicyName        = "Microsoft.DefaultV2"
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
    sku = {
      capacity = 10
      name     = "DataZoneStandard"
    }
  }
  name      = "text-embedding-3-small-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
}
resource "azapi_resource" "res-14" {
  response_export_values = ["identity.principalId"]
  body = {
    properties = {}
  }
  location  = "eastus2"
  name      = "aifproj-icenter-sbx"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-15" {
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "AppInsights"
      credentials   = var.secret_foundry_res_15_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        ApiType    = "Azure"
        ResourceId = "${var.ref_observability_res_5_id}"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "${var.ref_observability_res_5_id}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "appi-icenter-sandbox-neu-1893"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-16" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience      = "api://7f510755-760d-4b2f-a2ef-b45b9cd17a88"
      authType      = "ProjectManagedIdentity"
      category      = "RemoteTool"
      error         = null
      expiryTime    = null
      isDefault     = false
      isSharedToAll = false
      metadata = {
        toolEntityId = "azureml://location/eastus/apiCenter/registry-prod-bl/type/tools/objectId/azure-mcp-server/version/1"
        type         = "catalog_MCP"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_3_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-operations-sbx"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-17" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience                    = "api://930f18f1-5bac-4c6d-87de-80666eb36c9e"
      authType                    = "AgenticIdentityToken"
      category                    = "RemoteTool"
      error                       = null
      expiryTime                  = null
      isDefault                   = false
      isSharedToAll               = false
      metadata                    = {}
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_4_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-rglist-read-sbx"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-18" {
  # Explicit exception: exported identity auth types are documented by Microsoft.
  # Preserve authentication; embedded AzAPI 2.9.0 schema lacks these variants.
  schema_validation_enabled = false
  body = {
    properties = {
      audience                    = "api://${var.external_89b57f13a066}"
      authType                    = "AgenticIdentityToken"
      category                    = "RemoteTool"
      error                       = null
      expiryTime                  = null
      isDefault                   = false
      isSharedToAll               = false
      metadata                    = {}
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://${var.ref_container_apps_res_5_fqdn}"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "azure-mcp-vmstart-write-sbx"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-19" {
  body = {
    properties = {
      authType      = "CustomKeys"
      category      = "RemoteTool"
      credentials   = var.secret_foundry_res_19_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        knowledgeBaseName = "kb-icenter-support-sbx"
        type              = "knowledgeBase_MCP"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://srch-icenter-sbx-swc.search.windows.net/knowledgebases/kb-icenter-support-sbx/mcp?api-version=2026-05-01-preview"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "kb-kb-icenter-support--d5seg"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
resource "azapi_resource" "res-20" {
  body = {
    properties = {
      authType      = "ApiKey"
      category      = "CognitiveSearch"
      credentials   = var.secret_foundry_res_20_credentials
      error         = null
      expiryTime    = null
      isSharedToAll = false
      metadata = {
        ApiType              = "Azure"
        ApiVersion           = "2024-05-01-preview"
        DeploymentApiVersion = "2023-11-01"
        ResourceId           = "${var.ref_search_res_1_id}"
        displayName          = "srch-icenter-sbx-swc"
        type                 = "azure_ai_search"
      }
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      sharedUserList              = []
      target                      = "https://srch-icenter-sbx-swc.search.windows.net/"
      useWorkspaceManagedIdentity = false
    }
  }
  name      = "srchicentersbxswc0d5seg"
  parent_id = azapi_resource.res-14.id
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-10-01-preview"
}
