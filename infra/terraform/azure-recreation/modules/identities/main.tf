resource "azapi_resource" "res-1" {
  response_export_values = ["properties.clientId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-sql-runtime-icenter-sbx"
  parent_id              = var.ref_foundation_res_3_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-2" {
  response_export_values = ["properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-acr-pull-icenter-sbx"
  parent_id              = var.ref_foundation_res_5_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-3" {
  response_export_values = ["properties.clientId", "properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-ai-support-vmstart-write-sbx"
  parent_id              = var.ref_foundation_res_5_id
  tags = {
    product = "ai-support-platform"
    purpose = "f27-vmstart-write-executor"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-4" {
  response_export_values = ["properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-app-runtime-icenter-sbx"
  parent_id              = var.ref_foundation_res_5_id
  tags = {
    costCenter      = "inaki-poc"
    environment     = "sandbox"
    expiration      = "2026-09-05"
    identityPurpose = "id-app-runtime-icenter-sbx"
    managedBy       = "powershell-azure-cli"
    owner           = "icenter-microsoft"
    project         = "ai-support-platform"
    workload        = "integration"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-5" {
  response_export_values = ["properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-f27-correlation-attestor-sbx"
  parent_id              = var.ref_foundation_res_5_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-6" {
  response_export_values = ["properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-f27-custody-reader-sbx"
  parent_id              = var.ref_foundation_res_5_id
  tags = {
    f27-plan    = "F27_CUSTODIA_IDENTIDAD_BLOB_171_20261112"
    f27-purpose = "custody-reader"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-7" {
  response_export_values = ["properties.clientId", "properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-foundry-communication-icenter-sbx"
  parent_id              = var.ref_foundation_res_5_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-8" {
  body      = {}
  location  = "northeurope"
  name      = "id-mcp-read-icenter-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    costCenter      = "inaki-poc"
    environment     = "sandbox"
    expiration      = "2026-09-05"
    identityPurpose = "id-mcp-read-icenter-sbx"
    managedBy       = "powershell-azure-cli"
    owner           = "icenter-microsoft"
    project         = "ai-support-platform"
    workload        = "integration"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-9" {
  response_export_values = ["properties.clientId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-teams-runtime-icenter-sbx"
  parent_id              = var.ref_foundation_res_5_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-10" {
  response_export_values = ["properties.clientId", "properties.principalId"]
  body                   = {}
  location               = "northeurope"
  name                   = "id-vm-reader-icenter-sbx"
  parent_id              = var.ref_foundation_res_5_id
  type                   = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-11" {
  body      = {}
  location  = "northeurope"
  name      = "id-write-aks-icenter-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    costCenter      = "inaki-poc"
    environment     = "sandbox"
    expiration      = "2026-09-05"
    identityPurpose = "id-write-aks-icenter-sbx"
    managedBy       = "powershell-azure-cli"
    owner           = "icenter-microsoft"
    project         = "ai-support-platform"
    workload        = "integration"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-12" {
  body      = {}
  location  = "northeurope"
  name      = "id-write-vm-icenter-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    costCenter      = "inaki-poc"
    environment     = "sandbox"
    expiration      = "2026-09-05"
    identityPurpose = "id-write-vm-icenter-sbx"
    managedBy       = "powershell-azure-cli"
    owner           = "icenter-microsoft"
    project         = "ai-support-platform"
    workload        = "integration"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
resource "azapi_resource" "res-13" {
  body      = {}
  location  = "northeurope"
  name      = "id-write-webapp-icenter-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    costCenter      = "inaki-poc"
    environment     = "sandbox"
    expiration      = "2026-09-05"
    identityPurpose = "id-write-webapp-icenter-sbx"
    managedBy       = "powershell-azure-cli"
    owner           = "icenter-microsoft"
    project         = "ai-support-platform"
    workload        = "integration"
  }
  type = "Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview"
}
