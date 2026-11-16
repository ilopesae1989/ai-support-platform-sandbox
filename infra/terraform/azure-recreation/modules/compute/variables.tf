variable "subscription_id" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "ref_foundation_res_7_id" {
  type     = string
  nullable = false
}
variable "ref_network_res_10_id" {
  type     = string
  nullable = false
}

variable "vm_ssh_public_key" {
  type        = string
  nullable    = false
  description = "SSH public key for the recreated demo VM; provide your own public key."
}
