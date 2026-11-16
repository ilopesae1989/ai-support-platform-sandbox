module "access" {
  source                                = "./modules/access"
  providers                             = { azapi = azapi }
  subscription_id                       = var.subscription_id
  tenant_id                             = var.tenant_id
  external_00f78361ed27                 = var.external_00f78361ed27
  external_1da5714fc9be                 = var.external_1da5714fc9be
  external_4121e1e92d22                 = var.external_4121e1e92d22
  external_424f9d09392f                 = var.external_424f9d09392f
  external_427d2b2256ac                 = var.external_427d2b2256ac
  external_52d03af37df9                 = var.external_52d03af37df9
  external_6250ce61e3a8                 = var.external_6250ce61e3a8
  external_642543bf73c0                 = var.external_642543bf73c0
  external_d344e786d136                 = var.external_d344e786d136
  external_febfcad5c8ab                 = var.external_febfcad5c8ab
  ref_compute_res_3_id                  = module.compute.res_3_id
  ref_container_apps_res_3_principal_id = module.container_apps.res_3_principal_id
  ref_container_apps_res_4_principal_id = module.container_apps.res_4_principal_id
  ref_foundation_res_2_id               = module.foundation.res_2_id
  ref_foundation_res_3_id               = module.foundation.res_3_id
  ref_foundation_res_4_id               = module.foundation.res_4_id
  ref_foundation_res_6_id               = module.foundation.res_6_id
  ref_foundation_res_7_id               = module.foundation.res_7_id
  ref_foundry_res_14_id                 = module.foundry.res_14_id
  ref_foundry_res_14_principal_id       = module.foundry.res_14_principal_id
  ref_identities_res_10_principal_id    = module.identities.res_10_principal_id
  ref_identities_res_2_principal_id     = module.identities.res_2_principal_id
  ref_identities_res_3_principal_id     = module.identities.res_3_principal_id
  ref_identities_res_4_principal_id     = module.identities.res_4_principal_id
  ref_identities_res_5_principal_id     = module.identities.res_5_principal_id
  ref_identities_res_6_principal_id     = module.identities.res_6_principal_id
  ref_identities_res_7_principal_id     = module.identities.res_7_principal_id
  ref_key_vault_res_1_id                = module.key_vault.res_1_id
  ref_messaging_res_1_id                = module.messaging.res_1_id
  ref_observability_res_5_id            = module.observability.res_5_id
  ref_observability_res_6_id            = module.observability.res_6_id
  ref_registry_res_1_id                 = module.registry.res_1_id
  ref_search_res_1_id                   = module.search.res_1_id
  ref_storage_res_22_id                 = module.storage.res_22_id
  ref_storage_res_35_id                 = module.storage.res_35_id
}

module "app_services" {
  source                  = "./modules/app_services"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_2_id = module.foundation.res_2_id
}

module "bots" {
  source                        = "./modules/bots"
  providers                     = { azapi = azapi }
  subscription_id               = var.subscription_id
  tenant_id                     = var.tenant_id
  external_15e21363cbc3         = var.external_15e21363cbc3
  ref_container_apps_res_1_fqdn = module.container_apps.res_1_fqdn
  ref_foundation_res_2_id       = module.foundation.res_2_id
}

module "compute" {
  vm_ssh_public_key       = var.vm_ssh_public_key
  source                  = "./modules/compute"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_7_id = module.foundation.res_7_id
  ref_network_res_10_id   = module.network.res_10_id
}

module "container_apps" {
  mcp_read_application_client_id               = var.mcp_read_application_client_id
  mcp_legacy_application_client_id             = var.mcp_legacy_application_client_id
  teams_authorized_technicians_group_object_id = var.teams_authorized_technicians_group_object_id
  teams_authorization_identity_mappings_json   = var.teams_authorization_identity_mappings_json
  teams_channel_tenant_id                      = var.teams_channel_tenant_id
  source                                       = "./modules/container_apps"
  providers                                    = { azapi = azapi }
  subscription_id                              = var.subscription_id
  tenant_id                                    = var.tenant_id
  external_15e21363cbc3                        = var.external_15e21363cbc3
  external_89b57f13a066                        = var.external_89b57f13a066
  ref_foundation_res_2_id                      = module.foundation.res_2_id
  ref_foundation_res_5_id                      = module.foundation.res_5_id
  ref_identities_res_10_client_id              = module.identities.res_10_client_id
  ref_identities_res_10_id                     = module.identities.res_10_id
  ref_identities_res_1_client_id               = module.identities.res_1_client_id
  ref_identities_res_1_id                      = module.identities.res_1_id
  ref_identities_res_2_id                      = module.identities.res_2_id
  ref_identities_res_3_client_id               = module.identities.res_3_client_id
  ref_identities_res_3_id                      = module.identities.res_3_id
  ref_identities_res_7_client_id               = module.identities.res_7_client_id
  ref_identities_res_7_id                      = module.identities.res_7_id
  ref_identities_res_9_client_id               = module.identities.res_9_client_id
  ref_identities_res_9_id                      = module.identities.res_9_id
  ref_network_res_9_id                         = module.network.res_9_id
  ref_registry_res_1_login_server              = module.registry.res_1_login_server
  secret_container_apps_res_1_secrets          = var.secret_container_apps_res_1_secrets
  secret_container_apps_res_3_secrets          = var.secret_container_apps_res_3_secrets
  secret_container_apps_res_4_secrets          = var.secret_container_apps_res_4_secrets
  secret_container_apps_res_5_secrets          = var.secret_container_apps_res_5_secrets
}

module "foundation" {
  source          = "./modules/foundation"
  providers       = { azapi = azapi }
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

module "foundry" {
  source                            = "./modules/foundry"
  providers                         = { azapi = azapi }
  subscription_id                   = var.subscription_id
  tenant_id                         = var.tenant_id
  external_89b57f13a066             = var.external_89b57f13a066
  ref_container_apps_res_3_fqdn     = module.container_apps.res_3_fqdn
  ref_container_apps_res_4_fqdn     = module.container_apps.res_4_fqdn
  ref_container_apps_res_5_fqdn     = module.container_apps.res_5_fqdn
  ref_foundation_res_2_id           = module.foundation.res_2_id
  ref_foundation_res_4_id           = module.foundation.res_4_id
  ref_observability_res_5_id        = module.observability.res_5_id
  ref_search_res_1_id               = module.search.res_1_id
  secret_foundry_res_15_credentials = var.secret_foundry_res_15_credentials
  secret_foundry_res_19_credentials = var.secret_foundry_res_19_credentials
  secret_foundry_res_20_credentials = var.secret_foundry_res_20_credentials
  secret_foundry_res_4_credentials  = var.secret_foundry_res_4_credentials
  secret_foundry_res_8_credentials  = var.secret_foundry_res_8_credentials
  secret_foundry_res_9_credentials  = var.secret_foundry_res_9_credentials
}

module "identities" {
  source                  = "./modules/identities"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_3_id = module.foundation.res_3_id
  ref_foundation_res_5_id = module.foundation.res_5_id
}

module "integration" {
  office365_connection_display_name = var.office365_connection_display_name
  source                            = "./modules/integration"
  providers                         = { azapi = azapi }
  subscription_id                   = var.subscription_id
  tenant_id                         = var.tenant_id
  ref_foundation_res_5_id           = module.foundation.res_5_id
}

module "key_vault" {
  source                  = "./modules/key_vault"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_3_id = module.foundation.res_3_id
}

module "messaging" {
  source                  = "./modules/messaging"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_5_id = module.foundation.res_5_id
}

module "network" {
  source                  = "./modules/network"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_1_id = module.foundation.res_1_id
  ref_foundation_res_5_id = module.foundation.res_5_id
  ref_foundation_res_7_id = module.foundation.res_7_id
  ref_sql_res_1_id        = module.sql.res_1_id
}

module "observability" {
  alerts_email_address        = var.alerts_email_address
  source                      = "./modules/observability"
  providers                   = { azapi = azapi }
  subscription_id             = var.subscription_id
  tenant_id                   = var.tenant_id
  ref_container_apps_res_7_id = module.container_apps.res_7_id
  ref_foundation_res_6_id     = module.foundation.res_6_id
}

module "registry" {
  source                  = "./modules/registry"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_5_id = module.foundation.res_5_id
}

module "search" {
  source                  = "./modules/search"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_3_id = module.foundation.res_3_id
}

module "sql" {
  sql_entra_admin_login   = var.sql_entra_admin_login
  source                  = "./modules/sql"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  external_00f78361ed27   = var.external_00f78361ed27
  ref_foundation_res_3_id = module.foundation.res_3_id
}

module "storage" {
  source                  = "./modules/storage"
  providers               = { azapi = azapi }
  subscription_id         = var.subscription_id
  tenant_id               = var.tenant_id
  ref_foundation_res_2_id = module.foundation.res_2_id
  ref_foundation_res_3_id = module.foundation.res_3_id
  ref_foundation_res_6_id = module.foundation.res_6_id
}
