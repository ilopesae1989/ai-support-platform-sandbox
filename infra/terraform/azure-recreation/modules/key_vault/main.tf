resource "azapi_resource" "res-1" {
  body = {
    properties = {
      accessPolicies               = []
      enablePurgeProtection        = true
      enableRbacAuthorization      = true
      enableSoftDelete             = true
      enabledForDeployment         = false
      enabledForDiskEncryption     = false
      enabledForTemplateDeployment = false
      provisioningState            = "Succeeded"
      publicNetworkAccess          = "Enabled"
      sku = {
        family = "A"
        name   = "standard"
      }
      softDeleteRetentionInDays = 7
      tenantId                  = "${var.tenant_id}"
      vaultUri                  = "https://kv-icenter-sbx-neu.vault.azure.net/"
    }
  }
  location  = "northeurope"
  name      = "kv-icenter-sbx-neu"
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
  type = "Microsoft.KeyVault/vaults@2026-03-01-preview"
}
