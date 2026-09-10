param sqlServerName string
param sqlDatabaseName string
param location string
param sqlRuntimeIdentityName string
param sqlEntraAdminLogin string
param sqlEntraAdminObjectId string
param tenantId string
param databaseSkuName string
param databaseSkuTier string
param databaseSkuCapacity int
param databaseMaxSizeBytes int

resource sqlRuntimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: sqlRuntimeIdentityName
  location: location
}

resource sqlServer 'Microsoft.Sql/servers@2025-01-01' = {
  name: sqlServerName
  location: location
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: sqlEntraAdminLogin
      principalType: 'User'
      sid: sqlEntraAdminObjectId
      tenantId: tenantId
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    version: '12.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2025-01-01' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  sku: {
    name: databaseSkuName
    tier: databaseSkuTier
    capacity: databaseSkuCapacity
  }
  properties: {
    maxSizeBytes: databaseMaxSizeBytes
  }
}

output sqlServerId string = sqlServer.id
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabase.name
output sqlRuntimeIdentityId string = sqlRuntimeIdentity.id
output sqlRuntimeIdentityClientId string = sqlRuntimeIdentity.properties.clientId
output sqlRuntimeIdentityPrincipalId string = sqlRuntimeIdentity.properties.principalId