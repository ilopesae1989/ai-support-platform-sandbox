// Dedicated read-only custody identity; no signer or governor authority.
targetScope = 'resourceGroup'
param location string = resourceGroup().location
param name string = 'id-f27-custody-reader-sbx'
resource reader 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}
output resourceId string = reader.id
output clientId string = reader.properties.clientId
output principalId string = reader.properties.principalId
