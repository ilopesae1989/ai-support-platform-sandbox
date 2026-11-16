resource "azapi_resource" "res-1" {
  body = {
    properties = {
      administratorLogin = "CloudSA3331470a"
      administrators = {
        administratorType         = "ActiveDirectory"
        azureADOnlyAuthentication = true
        login                     = var.sql_entra_admin_login
        principalType             = "Group"
        sid                       = "${var.external_00f78361ed27}"
        tenantId                  = "${var.tenant_id}"
      }
      minimalTlsVersion             = "1.2"
      publicNetworkAccess           = "Enabled"
      restrictOutboundNetworkAccess = "Disabled"
      retentionDays                 = -1
      version                       = "12.0"
    }
  }
  location  = "eastus2"
  name      = "sql-icenter-app-sbx-eus2-557fda"
  parent_id = var.ref_foundation_res_3_id
  type      = "Microsoft.Sql/servers@2024-11-01-preview"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      administratorType = "ActiveDirectory"
      login             = var.sql_entra_admin_login
      sid               = "${var.external_00f78361ed27}"
      tenantId          = "${var.tenant_id}"
    }
  }
  name      = "ActiveDirectory"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Sql/servers/administrators@2024-11-01-preview"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      azureADOnlyAuthentication = true
    }
  }
  name      = "Default"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Sql/servers/azureADOnlyAuthentications@2024-11-01-preview"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      state = "Disabled"
    }
  }
  name      = "Current"
  parent_id = "${azapi_resource.res-1.id}/databases/master"
  type      = "Microsoft.Sql/servers/databases/transparentDataEncryption@2024-11-01-preview"
}
resource "azapi_resource" "res-5" {
  body = {
    properties = {
      availabilityZone                 = "NoPreference"
      catalogCollation                 = "SQL_Latin1_General_CP1_CI_AS"
      collation                        = "SQL_Latin1_General_CP1_CI_AS"
      isLedgerOn                       = false
      maintenanceConfigurationId       = "/subscriptions/${var.subscription_id}/providers/Microsoft.Maintenance/publicMaintenanceConfigurations/SQL_Default"
      maxSizeBytes                     = 2147483648
      readScale                        = "Disabled"
      requestedBackupStorageRedundancy = "Geo"
      zoneRedundant                    = false
    }
    sku = {
      capacity = 5
      name     = "Basic"
      tier     = "Basic"
    }
  }
  location  = "eastus2"
  name      = "sqldb-ai-support-platform-sbx"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Sql/servers/databases@2024-11-01-preview"
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {
      monthlyRetention      = "PT0S"
      timeBasedImmutability = "Disabled"
      weekOfYear            = 0
      weeklyRetention       = "PT0S"
      yearlyRetention       = "PT0S"
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-5.id
  type      = "Microsoft.Sql/servers/databases/backupLongTermRetentionPolicies@2024-11-01-preview"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      diffBackupIntervalInHours = 24
      retentionDays             = 7
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-5.id
  type      = "Microsoft.Sql/servers/databases/backupShortTermRetentionPolicies@2024-11-01-preview"
}
resource "azapi_resource" "res-8" {
  body = {
    properties = {
      scanState = "Complete"
      state     = "Enabled"
    }
  }
  name      = "Current"
  parent_id = azapi_resource.res-5.id
  type      = "Microsoft.Sql/servers/databases/transparentDataEncryption@2024-11-01-preview"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      autoRotationEnabled = false
      serverKeyName       = "ServiceManaged"
      serverKeyType       = "ServiceManaged"
    }
  }
  name      = "current"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Sql/servers/encryptionProtector@2024-11-01-preview"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      endIpAddress   = "88.4.159.3"
      startIpAddress = "88.4.159.3"
    }
  }
  name      = "ClientIPAddress_2026-11-12_15-1-3"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.Sql/servers/firewallRules@2024-11-01-preview"
}
