resource "azapi_resource" "res-1" {
  body = {
    kind = "functionapp"
    properties = {
      asyncScalingEnabled       = false
      elasticScaleEnabled       = false
      freeOfferExpirationTime   = null
      hostingEnvironmentProfile = null
      hyperV                    = false
      isCustomMode              = false
      isSpot                    = false
      isXenon                   = false
      kubeEnvironmentProfile    = null
      maximumElasticWorkerCount = 1
      perSiteScaling            = false
      reserved                  = true
      spotExpirationTime        = null
      targetWorkerCount         = 0
      targetWorkerSizeId        = 0
      workerTierName            = null
      zoneRedundant             = false
    }
    sku = {
      capacity = 0
      family   = "FC"
      name     = "FC1"
      size     = "FC1"
      tier     = "FlexConsumption"
    }
  }
  location  = "northeurope"
  name      = "ASP-rgicentersandboxapplication-2823"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Web/serverfarms@2025-03-01"
}
resource "azapi_resource" "res-2" {
  body = {
    kind = "functionapp"
    properties = {
      asyncScalingEnabled       = false
      elasticScaleEnabled       = false
      freeOfferExpirationTime   = null
      hostingEnvironmentProfile = null
      hyperV                    = false
      isCustomMode              = false
      isSpot                    = false
      isXenon                   = false
      kubeEnvironmentProfile    = null
      maximumElasticWorkerCount = 1
      perSiteScaling            = false
      reserved                  = true
      spotExpirationTime        = null
      targetWorkerCount         = 0
      targetWorkerSizeId        = 0
      workerTierName            = null
      zoneRedundant             = false
    }
    sku = {
      capacity = 0
      family   = "FC"
      name     = "FC1"
      size     = "FC1"
      tier     = "FlexConsumption"
    }
  }
  location  = "northeurope"
  name      = "ASP-rgicentersandboxapplication-3b3c"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Web/serverfarms@2025-03-01"
}
resource "azapi_resource" "res-3" {
  body = {
    kind = "linux"
    properties = {
      asyncScalingEnabled       = false
      elasticScaleEnabled       = false
      freeOfferExpirationTime   = "2026-09-12T07:43:54.7"
      hostingEnvironmentProfile = null
      hyperV                    = false
      isCustomMode              = false
      isSpot                    = false
      isXenon                   = false
      kubeEnvironmentProfile    = null
      maximumElasticWorkerCount = 1
      perSiteScaling            = false
      reserved                  = true
      spotExpirationTime        = null
      targetWorkerCount         = 0
      targetWorkerSizeId        = 0
      workerTierName            = null
      zoneRedundant             = false
    }
    sku = {
      capacity = 1
      family   = "B"
      name     = "B1"
      size     = "B1"
      tier     = "Basic"
    }
  }
  location  = "canadacentral"
  name      = "ASP-rgicentersandboxapplication-9d42"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Web/serverfarms@2025-03-01"
}
resource "azapi_resource" "res-4" {
  body = {
    kind = "functionapp"
    properties = {
      asyncScalingEnabled       = false
      elasticScaleEnabled       = false
      freeOfferExpirationTime   = null
      hostingEnvironmentProfile = null
      hyperV                    = false
      isCustomMode              = false
      isSpot                    = false
      isXenon                   = false
      kubeEnvironmentProfile    = null
      maximumElasticWorkerCount = 1
      perSiteScaling            = false
      reserved                  = true
      spotExpirationTime        = null
      targetWorkerCount         = 0
      targetWorkerSizeId        = 0
      workerTierName            = null
      zoneRedundant             = false
    }
    sku = {
      capacity = 0
      family   = "FC"
      name     = "FC1"
      size     = "FC1"
      tier     = "FlexConsumption"
    }
  }
  location  = "northeurope"
  name      = "ASP-rgicentersandboxapplication-f76d"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Web/serverfarms@2025-03-01"
}
