variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "external_15e21363cbc3" {
  type     = string
  nullable = false
}
variable "external_89b57f13a066" {
  type     = string
  nullable = false
}
variable "ref_foundation_res_2_id" {
  type     = string
  nullable = false
}
variable "ref_foundation_res_5_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_10_client_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_10_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_1_client_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_1_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_2_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_3_client_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_3_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_7_client_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_7_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_9_client_id" {
  type     = string
  nullable = false
}
variable "ref_identities_res_9_id" {
  type     = string
  nullable = false
}
variable "ref_network_res_9_id" {
  type     = string
  nullable = false
}
variable "ref_registry_res_1_login_server" {
  type     = string
  nullable = false
}
variable "secret_container_apps_res_1_secrets" {
  type      = any
  nullable  = false
  sensitive = true
}
variable "secret_container_apps_res_3_secrets" {
  type      = any
  nullable  = false
  sensitive = true
}
variable "secret_container_apps_res_4_secrets" {
  type      = any
  nullable  = false
  sensitive = true
}
variable "secret_container_apps_res_5_secrets" {
  type      = any
  nullable  = false
  sensitive = true
}

variable "teams_channel_tenant_id" {
  type        = string
  nullable    = false
  description = "Reviewed runtime value for TEAMS_CHANNEL_TENANT_ID on ca-app-runtime-icenter-sbx."
}

variable "teams_authorization_identity_mappings_json" {
  type        = string
  nullable    = false
  description = "Reviewed runtime value for TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON on ca-app-runtime-icenter-sbx."
  sensitive   = true
}

variable "teams_authorized_technicians_group_object_id" {
  type        = string
  nullable    = false
  description = "Reviewed runtime value for TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID on ca-app-runtime-icenter-sbx."
}

variable "mcp_legacy_application_client_id" {
  type        = string
  nullable    = false
  description = "Reviewed runtime value for AzureAd__ClientId on azure-mcp-operations-server."
}

variable "mcp_read_application_client_id" {
  type        = string
  nullable    = false
  description = "Reviewed runtime value for AzureAd__ClientId on azure-mcp-rglist-read-sbx."
}
