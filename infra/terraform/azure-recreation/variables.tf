variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "external_00f78361ed27" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_15e21363cbc3" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_1da5714fc9be" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_4121e1e92d22" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_424f9d09392f" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_427d2b2256ac" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_52d03af37df9" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_6250ce61e3a8" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_642543bf73c0" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_89b57f13a066" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_d344e786d136" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "external_febfcad5c8ab" {
  type        = string
  nullable    = false
  description = "Entra identity outside the recreated resource graph"
}
variable "secret_container_apps_res_1_secrets" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Container Apps secrets omitted by GET; supply list or explicitly reviewed empty list"
}
variable "secret_container_apps_res_3_secrets" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Container Apps secrets omitted by GET; supply list or explicitly reviewed empty list"
}
variable "secret_container_apps_res_4_secrets" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Container Apps secrets omitted by GET; supply list or explicitly reviewed empty list"
}
variable "secret_container_apps_res_5_secrets" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Container Apps secrets omitted by GET; supply list or explicitly reviewed empty list"
}
variable "secret_foundry_res_15_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}
variable "secret_foundry_res_19_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}
variable "secret_foundry_res_20_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}
variable "secret_foundry_res_4_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}
variable "secret_foundry_res_8_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}
variable "secret_foundry_res_9_credentials" {
  type        = any
  nullable    = false
  sensitive   = true
  description = "Foundry credentials omitted by GET"
}

variable "vm_ssh_public_key" {
  type        = string
  nullable    = false
  description = "SSH public key for the recreated demo VM; provide your own public key."
}

variable "sql_entra_admin_login" {
  type        = string
  nullable    = false
  description = "Display/login name of the reviewed SQL Entra administrator."
  sensitive   = true
}

variable "alerts_email_address" {
  type        = string
  nullable    = false
  description = "Email recipient for the action group."
  sensitive   = true
}

variable "office365_connection_display_name" {
  type        = string
  nullable    = false
  description = "Display name of the Office 365 connection; authorization must be restored separately."
  sensitive   = true
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
