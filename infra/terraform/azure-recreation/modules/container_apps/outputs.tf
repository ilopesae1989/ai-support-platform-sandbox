output "res_1_fqdn" {
  value = azapi_resource.res-1.output.properties.configuration.ingress.fqdn
}
output "res_3_fqdn" {
  value = azapi_resource.res-3.output.properties.configuration.ingress.fqdn
}
output "res_3_principal_id" {
  value = azapi_resource.res-3.output.identity.principalId
}
output "res_4_fqdn" {
  value = azapi_resource.res-4.output.properties.configuration.ingress.fqdn
}
output "res_4_principal_id" {
  value = azapi_resource.res-4.output.identity.principalId
}
output "res_5_fqdn" {
  value = azapi_resource.res-5.output.properties.configuration.ingress.fqdn
}
output "res_5_id" {
  value = azapi_resource.res-5.id
}
output "res_7_id" {
  value = azapi_resource.res-7.id
}
