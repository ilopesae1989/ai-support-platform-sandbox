resource "azapi_resource" "res-1" {
  body = {
    etag = "\"25030068-0000-0d00-0000-6aab87320000\""
    kind = "azurebot"
    properties = {
      allSettings                       = null
      appPasswordHint                   = null
      cmekKeyVaultUrl                   = null
      description                       = "Microsoft Teams channel for AI Support Platform sandbox"
      developerAppInsightKey            = null
      developerAppInsightsApplicationId = null
      disableLocalAuth                  = false
      displayName                       = "AI Support Platform Teams SBX"
      endpoint                          = "https://${var.ref_container_apps_res_1_fqdn}/api/messages"
      iconUrl                           = "https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png"
      isCmekEnabled                     = false
      isStreamingSupported              = false
      luisAppIds                        = []
      manifestUrl                       = null
      msaAppId                          = "${var.external_15e21363cbc3}"
      msaAppMSIResourceId               = null
      msaAppTenantId                    = "${var.tenant_id}"
      msaAppType                        = "SingleTenant"
      openWithHint                      = null
      parameters                        = null
      publicNetworkAccess               = "Enabled"
      publishingCredentials             = null
      schemaTransformationVersion       = "1.3"
      storageResourceId                 = null
      tenantId                          = "${var.tenant_id}"
    }
    sku = {
      name = "F0"
    }
  }
  location  = "global"
  name      = "bot-ai-support-platform-teams-sbx"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.BotService/botServices@2023-09-15-preview"
}
