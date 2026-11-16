provider "azapi" {
  subscription_id            = var.subscription_id
  tenant_id                  = var.tenant_id
  environment                = "public"
  use_cli                    = true
  use_msi                    = false
  use_oidc                   = false
  skip_provider_registration = true
}
