variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "ref_foundation_res_5_id" {
  type     = string
  nullable = false
}

variable "office365_connection_display_name" {
  type        = string
  nullable    = false
  description = "Display name of the Office 365 connection; authorization must be restored separately."
  sensitive   = true
}
