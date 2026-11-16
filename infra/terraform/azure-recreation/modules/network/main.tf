resource "azapi_resource" "res-1" {
  body = {
    properties = {
    }
  }
  location  = "eastus2"
  name      = "NetworkWatcher_eastus2"
  parent_id = var.ref_foundation_res_1_id
  type      = "Microsoft.Network/networkWatchers@2025-05-01"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
    }
  }
  location  = "northeurope"
  name      = "NetworkWatcher_northeurope"
  parent_id = var.ref_foundation_res_1_id
  type      = "Microsoft.Network/networkWatchers@2025-05-01"
}
resource "azapi_resource" "res-3" {
  body = {
    etag       = "af6a0ce4-86c8-443e-bf50-117b9e226e5d"
    properties = {}
  }
  location  = "global"
  name      = "privatelink.database.windows.net"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Network/privateDnsZones@2024-06-01"
}
resource "azapi_resource" "res-4" {
  body = {
    etag = "eb4875a0-3cff-4481-9214-6a0f8cd480e3"
    properties = {
      aRecords = [{
        ipv4Address = "10.240.0.68"
      }]
      metadata = {
        creator = "created by private endpoint pe-sql-app-runtime-icenter-sbx with resource guid 7466895a-355a-4353-8f8e-ead8366cc086"
      }
      ttl = 10
    }
  }
  name      = "sql-icenter-app-sbx-eus2-557fda"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.Network/privateDnsZones/A@2024-06-01"
}
resource "azapi_resource" "res-5" {
  body = {
    etag = "06ca5cb8-0baf-4c62-9ea7-a04d426f0c80"
    properties = {
      soaRecord = {
        email        = "azureprivatedns-host.microsoft.com"
        expireTime   = 2419200
        host         = "azureprivatedns.net"
        minimumTtl   = 10
        refreshTime  = 3600
        retryTime    = 300
        serialNumber = 1
      }
      ttl = 3600
    }
  }
  name      = "@"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.Network/privateDnsZones/SOA@2024-06-01"
}
resource "azapi_resource" "res-6" {
  body = {
    etag = "\"4500aced-0000-0100-0000-6aa3cd8d0000\""
    properties = {
      registrationEnabled = false
      resolutionPolicy    = "Default"
      virtualNetwork = {
        id = azapi_resource.res-9.id
      }
    }
  }
  location  = "global"
  name      = "vnet-app-runtime-icenter-sbx-ne-sql-dns-link"
  parent_id = azapi_resource.res-3.id
  type      = "Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      customDnsConfigs                    = []
      customNetworkInterfaceName          = ""
      ipConfigurations                    = []
      ipVersionType                       = "IPv4"
      manualPrivateLinkServiceConnections = []
      privateLinkServiceConnections = [{
        id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Network/privateEndpoints/pe-sql-app-runtime-icenter-sbx/privateLinkServiceConnections/pe-sql-app-runtime-icenter-sbx-sql"
        name = "pe-sql-app-runtime-icenter-sbx-sql"
        properties = {
          groupIds = ["sqlServer"]
          privateLinkServiceConnectionState = {
            actionsRequired = "None"
            description     = "Auto-approved"
            status          = "Approved"
          }
          privateLinkServiceId = "${var.ref_sql_res_1_id}"
        }
      }]
      subnet = {
        id = "${azapi_resource.res-9.id}/subnets/snet-private-endpoints"
      }
    }
  }
  location  = "northeurope"
  name      = "pe-sql-app-runtime-icenter-sbx"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Network/privateEndpoints@2025-05-01"
}
resource "azapi_resource" "res-8" {
  body = {
    properties = {
      privateDnsZoneConfigs = [{
        name = "sql"
        properties = {
          privateDnsZoneId = azapi_resource.res-3.id
        }
      }]
    }
  }
  name      = "default"
  parent_id = azapi_resource.res-7.id
  type      = "Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2025-05-01"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      addressSpace = {
        addressPrefixes = ["10.240.0.0/24"]
      }
      enableDdosProtection        = false
      privateEndpointVNetPolicies = "Disabled"
      subnets = [{
        id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Network/virtualNetworks/vnet-app-runtime-icenter-sbx-ne/subnets/snet-containerapps-runtime"
        name = "snet-containerapps-runtime"
        properties = {
          addressPrefix = "10.240.0.0/26"
          delegations = [{
            id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Network/virtualNetworks/vnet-app-runtime-icenter-sbx-ne/subnets/snet-containerapps-runtime/delegations/Microsoft.App-environments"
            name = "Microsoft.App-environments"
            properties = {
              serviceName = "Microsoft.App/environments"
            }
            type = "Microsoft.Network/virtualNetworks/subnets/delegations"
          }]
          privateEndpointNetworkPolicies    = "Disabled"
          privateLinkServiceNetworkPolicies = "Enabled"
        }
        }, {
        id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-integration/providers/Microsoft.Network/virtualNetworks/vnet-app-runtime-icenter-sbx-ne/subnets/snet-private-endpoints"
        name = "snet-private-endpoints"
        properties = {
          addressPrefix                     = "10.240.0.64/27"
          delegations                       = []
          privateEndpointNetworkPolicies    = "Disabled"
          privateLinkServiceNetworkPolicies = "Enabled"
        }
      }]
      virtualNetworkPeerings = []
    }
  }
  location  = "northeurope"
  name      = "vnet-app-runtime-icenter-sbx-ne"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.Network/virtualNetworks@2025-05-01"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      auxiliaryMode           = "None"
      auxiliarySku            = "None"
      disableTcpStateTracking = false
      dnsSettings = {
        dnsServers = []
      }
      enableAcceleratedNetworking = false
      enableIPForwarding          = false
      ipConfigurations = [{
        id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-vm-demo/providers/Microsoft.Network/networkInterfaces/nic-vm-icenter-sbx-demo-01/ipConfigurations/ipconfig1"
        name = "ipconfig1"
        properties = {
          primary                   = true
          privateIPAddress          = "10.17.1.4"
          privateIPAddressVersion   = "IPv4"
          privateIPAllocationMethod = "Dynamic"
          subnet = {
            id = "${azapi_resource.res-12.id}/subnets/snet-vm-demo"
          }
        }
      }]
      networkSecurityGroup = {
        id = azapi_resource.res-11.id
      }
      nicType = "Standard"
    }
  }
  location  = "eastus2"
  name      = "nic-vm-icenter-sbx-demo-01"
  parent_id = var.ref_foundation_res_7_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Network/networkInterfaces@2025-05-01"
}
resource "azapi_resource" "res-11" {
  body = {
    properties = {
      securityRules = []
    }
  }
  location  = "eastus2"
  name      = "nsg-icenter-sbx-vm-demo"
  parent_id = var.ref_foundation_res_7_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Network/networkSecurityGroups@2025-05-01"
}
resource "azapi_resource" "res-12" {
  body = {
    properties = {
      addressSpace = {
        addressPrefixes = ["10.17.0.0/16"]
      }
      enableDdosProtection        = false
      privateEndpointVNetPolicies = "Disabled"
      subnets = [{
        id   = "/subscriptions/${var.subscription_id}/resourceGroups/rg-icenter-sandbox-vm-demo/providers/Microsoft.Network/virtualNetworks/vnet-icenter-sbx-vm-demo/subnets/snet-vm-demo"
        name = "snet-vm-demo"
        properties = {
          addressPrefix                     = "10.17.1.0/24"
          defaultOutboundAccess             = false
          delegations                       = []
          privateEndpointNetworkPolicies    = "Disabled"
          privateLinkServiceNetworkPolicies = "Enabled"
        }
      }]
      virtualNetworkPeerings = []
    }
  }
  location  = "eastus2"
  name      = "vnet-icenter-sbx-vm-demo"
  parent_id = var.ref_foundation_res_7_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Network/virtualNetworks@2025-05-01"
}
