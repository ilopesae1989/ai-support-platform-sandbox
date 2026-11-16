resource "azapi_resource" "res-1" {
  body = {
    kind = "StorageV2"
    properties = {
      accessTier                  = "Hot"
      allowBlobPublicAccess       = false
      allowCrossTenantReplication = false
      encryption = {
        keySource = "Microsoft.Storage"
        services = {
          blob = {
            enabled = true
            keyType = "Account"
          }
          file = {
            enabled = true
            keyType = "Account"
          }
        }
      }
      minimumTlsVersion = "TLS1_2"
      networkAcls = {
        bypass              = "None"
        defaultAction       = "Allow"
        ipRules             = []
        ipv6Rules           = []
        virtualNetworkRules = []
      }
      supportsHttpsTrafficOnly = true
    }
    sku = {
      name = "Standard_LRS"
    }
  }
  location  = "northeurope"
  name      = "stfnnormsbx557fda"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Storage/storageAccounts@2025-06-01"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      deleteRetentionPolicy = {
        allowPermanentDelete = false
        enabled              = false
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Storage/storageAccounts/blobServices@2025-06-01"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-hosts"
  parent_id = azapi_resource.res-2.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-secrets"
  parent_id = azapi_resource.res-2.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-5" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      protocolSettings = {
        smb = {}
      }
      shareDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Storage/storageAccounts/fileServices@2025-06-01"
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Storage/storageAccounts/queueServices@2025-06-01"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Storage/storageAccounts/tableServices@2025-06-01"
}
resource "azapi_resource" "res-8" {
  body = {
    kind = "StorageV2"
    properties = {
      accessTier                  = "Hot"
      allowBlobPublicAccess       = false
      allowCrossTenantReplication = false
      encryption = {
        keySource = "Microsoft.Storage"
        services = {
          blob = {
            enabled = true
            keyType = "Account"
          }
          file = {
            enabled = true
            keyType = "Account"
          }
        }
      }
      minimumTlsVersion = "TLS1_2"
      networkAcls = {
        bypass              = "None"
        defaultAction       = "Allow"
        ipRules             = []
        ipv6Rules           = []
        virtualNetworkRules = []
      }
      supportsHttpsTrafficOnly = true
    }
    sku = {
      name = "Standard_LRS"
    }
  }
  location  = "northeurope"
  name      = "stfnorchsbx557fda"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Storage/storageAccounts@2025-06-01"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      deleteRetentionPolicy = {
        allowPermanentDelete = false
        enabled              = false
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.Storage/storageAccounts/blobServices@2025-06-01"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-hosts"
  parent_id = azapi_resource.res-9.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-11" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-secrets"
  parent_id = azapi_resource.res-9.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-12" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      protocolSettings = {
        smb = {}
      }
      shareDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.Storage/storageAccounts/fileServices@2025-06-01"
}
resource "azapi_resource" "res-13" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.Storage/storageAccounts/queueServices@2025-06-01"
}
resource "azapi_resource" "res-14" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.Storage/storageAccounts/tableServices@2025-06-01"
}
resource "azapi_resource" "res-15" {
  body = {
    kind = "StorageV2"
    properties = {
      accessTier                  = "Hot"
      allowBlobPublicAccess       = false
      allowCrossTenantReplication = false
      encryption = {
        keySource = "Microsoft.Storage"
        services = {
          blob = {
            enabled = true
            keyType = "Account"
          }
          file = {
            enabled = true
            keyType = "Account"
          }
        }
      }
      minimumTlsVersion = "TLS1_2"
      networkAcls = {
        bypass              = "None"
        defaultAction       = "Allow"
        ipRules             = []
        ipv6Rules           = []
        virtualNetworkRules = []
      }
      supportsHttpsTrafficOnly = true
    }
    sku = {
      name = "Standard_LRS"
    }
  }
  location  = "northeurope"
  name      = "stfntoolssbx557fda"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Storage/storageAccounts@2025-06-01"
}
resource "azapi_resource" "res-16" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      deleteRetentionPolicy = {
        allowPermanentDelete = false
        enabled              = false
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-15.id
  type      = "Microsoft.Storage/storageAccounts/blobServices@2025-06-01"
}
resource "azapi_resource" "res-17" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-hosts"
  parent_id = azapi_resource.res-16.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-18" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "azure-webjobs-secrets"
  parent_id = azapi_resource.res-16.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-19" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      protocolSettings = {
        smb = {}
      }
      shareDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-15.id
  type      = "Microsoft.Storage/storageAccounts/fileServices@2025-06-01"
}
resource "azapi_resource" "res-20" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-15.id
  type      = "Microsoft.Storage/storageAccounts/queueServices@2025-06-01"
}
resource "azapi_resource" "res-21" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-15.id
  type      = "Microsoft.Storage/storageAccounts/tableServices@2025-06-01"
}
resource "azapi_resource" "res-22" {
  body = {
    kind = "StorageV2"
    properties = {
      accessTier                  = "Hot"
      allowBlobPublicAccess       = false
      allowCrossTenantReplication = false
      encryption = {
        keySource = "Microsoft.Storage"
        services = {
          blob = {
            enabled = true
            keyType = "Account"
          }
          file = {
            enabled = true
            keyType = "Account"
          }
        }
      }
      minimumTlsVersion = "TLS1_2"
      networkAcls = {
        bypass              = "None"
        defaultAction       = "Allow"
        ipRules             = []
        ipv6Rules           = []
        virtualNetworkRules = []
      }
      publicNetworkAccess      = "Enabled"
      supportsHttpsTrafficOnly = true
    }
    sku = {
      name = "Standard_LRS"
    }
  }
  location  = "northeurope"
  name      = "sticentersupportsbx"
  parent_id = var.ref_foundation_res_3_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "data"
  }
  type = "Microsoft.Storage/storageAccounts@2025-06-01"
}
resource "azapi_resource" "res-23" {
  body = {
    properties = {
      changeFeed = {
        enabled = false
      }
      containerDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
      cors = {
        corsRules = []
      }
      deleteRetentionPolicy = {
        allowPermanentDelete = false
        days                 = 7
        enabled              = true
      }
      isVersioningEnabled = false
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-22.id
  type      = "Microsoft.Storage/storageAccounts/blobServices@2025-06-01"
}
resource "azapi_resource" "res-24" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "evidence"
  parent_id = azapi_resource.res-23.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-25" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "exports"
  parent_id = azapi_resource.res-23.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-26" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "knowledge"
  parent_id = azapi_resource.res-23.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-27" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "raw-events"
  parent_id = azapi_resource.res-23.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-28" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "temporary"
  parent_id = azapi_resource.res-23.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-29" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      protocolSettings = {
        smb = {}
      }
      shareDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-22.id
  type      = "Microsoft.Storage/storageAccounts/fileServices@2025-06-01"
}
resource "azapi_resource" "res-30" {
  body = {
    properties = {
      policy = {
        rules = [{
          definition = {
            actions = {
              baseBlob = {
                delete = {
                  daysAfterModificationGreaterThan = 30
                }
              }
            }
            filters = {
              blobTypes   = ["blockBlob"]
              prefixMatch = ["raw-events/"]
            }
          }
          enabled = true
          name    = "delete-raw-events-after-30-days"
          type    = "Lifecycle"
          }, {
          definition = {
            actions = {
              baseBlob = {
                delete = {
                  daysAfterModificationGreaterThan = 30
                }
              }
            }
            filters = {
              blobTypes   = ["blockBlob"]
              prefixMatch = ["exports/"]
            }
          }
          enabled = true
          name    = "delete-exports-after-30-days"
          type    = "Lifecycle"
          }, {
          definition = {
            actions = {
              baseBlob = {
                delete = {
                  daysAfterModificationGreaterThan = 7
                }
              }
            }
            filters = {
              blobTypes   = ["blockBlob"]
              prefixMatch = ["temporary/"]
            }
          }
          enabled = true
          name    = "delete-temporary-after-7-days"
          type    = "Lifecycle"
        }]
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-22.id
  type      = "Microsoft.Storage/storageAccounts/managementPolicies@2025-06-01"
}
resource "azapi_resource" "res-31" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-22.id
  type      = "Microsoft.Storage/storageAccounts/queueServices@2025-06-01"
}
resource "azapi_resource" "res-32" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-22.id
  type      = "Microsoft.Storage/storageAccounts/tableServices@2025-06-01"
}
resource "azapi_resource" "res-33" {
  body = {
    kind = "StorageV2"
    properties = {
      accessTier                  = "Hot"
      allowBlobPublicAccess       = false
      allowCrossTenantReplication = false
      encryption = {
        keySource = "Microsoft.Storage"
        services = {
          blob = {
            enabled = true
            keyType = "Account"
          }
          file = {
            enabled = true
            keyType = "Account"
          }
        }
      }
      minimumTlsVersion = "TLS1_2"
      networkAcls = {
        bypass              = "AzureServices"
        defaultAction       = "Deny"
        ipRules             = []
        ipv6Rules           = []
        resourceAccessRules = []
        virtualNetworkRules = []
      }
      publicNetworkAccess      = "Enabled"
      supportsHttpsTrafficOnly = true
    }
    sku = {
      name = "Standard_LRS"
    }
  }
  location  = "northeurope"
  name      = "sticenterevidsbx557fda"
  parent_id = var.ref_foundation_res_6_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "monitoring-evidence"
  }
  type = "Microsoft.Storage/storageAccounts@2025-06-01"
}
resource "azapi_resource" "res-34" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      deleteRetentionPolicy = {
        allowPermanentDelete = false
        enabled              = false
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-33.id
  type      = "Microsoft.Storage/storageAccounts/blobServices@2025-06-01"
}
resource "azapi_resource" "res-35" {
  body = {
    properties = {
      defaultEncryptionScope      = "$account-encryption-key"
      denyEncryptionScopeOverride = false
      publicAccess                = "None"
    }
  }
  name      = "am-containerappconsolelogs"
  parent_id = azapi_resource.res-34.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01"
}
resource "azapi_resource" "res-36" {
  body = {
    properties = {
      allowProtectedAppendWrites            = true
      immutabilityPeriodSinceCreationInDays = 1
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-35.id
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers/immutabilityPolicies@2025-06-01"
}
resource "azapi_resource" "res-37" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
      protocolSettings = {
        smb = {}
      }
      shareDeleteRetentionPolicy = {
        days    = 7
        enabled = true
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-33.id
  type      = "Microsoft.Storage/storageAccounts/fileServices@2025-06-01"
}
resource "azapi_resource" "res-38" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-33.id
  type      = "Microsoft.Storage/storageAccounts/queueServices@2025-06-01"
}
resource "azapi_resource" "res-39" {
  body = {
    properties = {
      cors = {
        corsRules = []
      }
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-33.id
  type      = "Microsoft.Storage/storageAccounts/tableServices@2025-06-01"
}
