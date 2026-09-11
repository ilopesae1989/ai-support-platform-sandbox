targetScope = 'subscription'

param networkResourceGroupName string
param dataResourceGroupName string
param applicationResourceGroupName string
param location string
param vnetName string
param vnetAddressPrefix string
param containerAppsSubnetName string
param containerAppsSubnetPrefix string
param privateEndpointSubnetName string
param privateEndpointSubnetPrefix string
param privateDnsZoneName string
param sqlServerName string
param sqlDatabaseName string
param sqlRuntimeIdentityName string
param sqlEntraAdminLogin string
param sqlEntraAdminObjectId string
param tenantId string
param databaseSkuName string
param databaseSkuTier string
param databaseSkuCapacity int
param databaseMaxSizeBytes int
param privateEndpointName string
param environmentName string
param containerAppName string
param imageByDigest string
param registryServer string
param imagePullIdentityResourceId string
param teamsIdentityResourceId string
param azureVmReaderIdentityResourceId string
param foundryIdentityResourceId string
param containerCpu string
param containerMemory string
param clientId string
param teamsManagedIdentityClientId string
param teamsChannelTenantId string
param teamsAuthorizedTechniciansGroupObjectId string
param foundryProjectEndpoint string
param foundryManagedIdentityClientId string
param azureVmReaderManagedIdentityClientId string

module applicationNetwork './network/application-private-network.bicep' = {
  name: 'application-network'
  scope: resourceGroup(networkResourceGroupName)
  params: {
    vnetName: vnetName
    location: location
    vnetAddressPrefix: vnetAddressPrefix
    containerAppsSubnetName: containerAppsSubnetName
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    privateEndpointSubnetName: privateEndpointSubnetName
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
    privateDnsZoneName: privateDnsZoneName
  }
}

module applicationSql './sql/application-sql-foundation.bicep' = {
  name: 'application-sql'
  scope: resourceGroup(dataResourceGroupName)
  params: {
    sqlServerName: sqlServerName
    sqlDatabaseName: sqlDatabaseName
    location: location
    sqlRuntimeIdentityName: sqlRuntimeIdentityName
    sqlEntraAdminLogin: sqlEntraAdminLogin
    sqlEntraAdminObjectId: sqlEntraAdminObjectId
    tenantId: tenantId
    databaseSkuName: databaseSkuName
    databaseSkuTier: databaseSkuTier
    databaseSkuCapacity: databaseSkuCapacity
    databaseMaxSizeBytes: databaseMaxSizeBytes
  }
}

module applicationSqlPrivateLink './network/application-sql-private-link.bicep' = {
  name: 'application-sql-private-link'
  scope: resourceGroup(networkResourceGroupName)
  params: {
    privateEndpointName: privateEndpointName
    location: location
    privateEndpointSubnetId: applicationNetwork.outputs.privateEndpointSubnetId
    sqlServerResourceId: applicationSql.outputs.sqlServerId
    privateDnsZoneId: applicationNetwork.outputs.privateDnsZoneId
  }
}

module applicationHost './container-apps/application-host.bicep' = {
  name: 'application-host'
  scope: resourceGroup(applicationResourceGroupName)
  params: {
    environmentName: environmentName
    containerAppName: containerAppName
    location: location
    infrastructureSubnetId: applicationNetwork.outputs.containerAppsSubnetId
    imageByDigest: imageByDigest
    registryServer: registryServer
    imagePullIdentityResourceId: imagePullIdentityResourceId
    teamsIdentityResourceId: teamsIdentityResourceId
    azureSqlIdentityResourceId: applicationSql.outputs.sqlRuntimeIdentityId
    azureVmReaderIdentityResourceId: azureVmReaderIdentityResourceId
    foundryIdentityResourceId: foundryIdentityResourceId
    containerCpu: containerCpu
    containerMemory: containerMemory
    clientId: clientId
    teamsManagedIdentityClientId: teamsManagedIdentityClientId
    tenantId: tenantId
    teamsChannelTenantId: teamsChannelTenantId
    teamsAuthorizedTechniciansGroupObjectId: teamsAuthorizedTechniciansGroupObjectId
    azureSqlServer: applicationSql.outputs.sqlServerFqdn
    azureSqlDatabase: applicationSql.outputs.sqlDatabaseName
    azureSqlManagedIdentityClientId: applicationSql.outputs.sqlRuntimeIdentityClientId
    foundryProjectEndpoint: foundryProjectEndpoint
    foundryManagedIdentityClientId: foundryManagedIdentityClientId
    azureVmReaderManagedIdentityClientId: azureVmReaderManagedIdentityClientId
  }
}

output vnetId string = applicationNetwork.outputs.vnetId
output containerAppsSubnetId string = applicationNetwork.outputs.containerAppsSubnetId
output privateEndpointSubnetId string = applicationNetwork.outputs.privateEndpointSubnetId
output privateDnsZoneId string = applicationNetwork.outputs.privateDnsZoneId

output sqlServerId string = applicationSql.outputs.sqlServerId
output sqlServerFqdn string = applicationSql.outputs.sqlServerFqdn
output sqlDatabaseName string = applicationSql.outputs.sqlDatabaseName

output sqlRuntimeIdentityId string = applicationSql.outputs.sqlRuntimeIdentityId
output sqlRuntimeIdentityClientId string = applicationSql.outputs.sqlRuntimeIdentityClientId
output sqlRuntimeIdentityPrincipalId string = applicationSql.outputs.sqlRuntimeIdentityPrincipalId

output privateEndpointId string = applicationSqlPrivateLink.outputs.privateEndpointId

output environmentId string = applicationHost.outputs.environmentId
output containerAppId string = applicationHost.outputs.containerAppId
output containerAppFqdn string = applicationHost.outputs.containerAppFqdn