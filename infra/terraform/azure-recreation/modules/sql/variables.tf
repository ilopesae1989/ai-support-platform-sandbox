variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "external_00f78361ed27" {
  type     = string
  nullable = false
}
variable "ref_foundation_res_3_id" {
  type     = string
  nullable = false
}

variable "sql_entra_admin_login" {
  type        = string
  nullable    = false
  description = "Display/login name of the reviewed SQL Entra administrator."
  sensitive   = true
}
