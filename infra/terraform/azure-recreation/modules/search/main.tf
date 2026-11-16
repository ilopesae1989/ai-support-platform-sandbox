resource "azapi_resource" "res-1" {
  body = {
    properties = {
      authOptions = {
        apiKeyOnly = {}
      }
      computeType                 = "Default"
      dataExfiltrationProtections = []
      disableLocalAuth            = false
      encryptionWithCmk = {
        enforcement = "Unspecified"
      }
      endpoint    = "https://srch-icenter-sbx-swc.search.windows.net"
      hostingMode = "Default"
      networkRuleSet = {
        bypass  = "None"
        ipRules = []
      }
      partitionCount      = 1
      publicNetworkAccess = "Enabled"
      replicaCount        = 1
      semanticSearch      = "free"
      upgradeAvailable    = "notAvailable"
    }
    sku = {
      name = "free"
    }
  }
  location  = "swedencentral"
  name      = "srch-icenter-sbx-swc"
  parent_id = var.ref_foundation_res_3_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "knowledge"
  }
  type = "Microsoft.Search/searchServices@2025-05-01"
}
