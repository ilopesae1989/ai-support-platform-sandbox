variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "ref_container_apps_res_7_id" {
  type     = string
  nullable = false
}
variable "ref_foundation_res_6_id" {
  type     = string
  nullable = false
}

variable "alerts_email_address" {
  type        = string
  nullable    = false
  description = "Email recipient for the action group."
  sensitive   = true
}
