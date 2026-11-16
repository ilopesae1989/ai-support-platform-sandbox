resource "azapi_resource" "res-1" {
  body = {
    properties = {}
  }
  location  = "eastus2"
  name      = "NetworkWatcherRG"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {}
  }
  location  = "westeurope"
  name      = "rg-icenter-sandbox-application"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "application"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {}
  }
  location  = "westeurope"
  name      = "rg-icenter-sandbox-data"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "data"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {}
  }
  location  = "westeurope"
  name      = "rg-icenter-sandbox-foundry"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "foundry"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-5" {
  body = {
    properties = {}
  }
  location  = "westeurope"
  name      = "rg-icenter-sandbox-integration"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "integration"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {}
  }
  location  = "westeurope"
  name      = "rg-icenter-sandbox-operations"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "operations"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {}
  }
  location  = "eastus2"
  name      = "rg-icenter-sandbox-vm-demo"
  parent_id = "/subscriptions/${var.subscription_id}"
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Resources/resourceGroups@2025-04-01"
}
