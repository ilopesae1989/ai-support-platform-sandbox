output "res_1_id" {
  value = azapi_resource.res-1.id
}
output "res_1_login_server" {
  value = azapi_resource.res-1.output.properties.loginServer
}
