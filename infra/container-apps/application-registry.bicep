param registryName string
param location string
param imagePullIdentityName string
param repositoryName string

var repositoryReaderRoleDefinitionId = 'b93aa761-3e63-49ed-ac28-beffa264f7ac'

var repositoryReaderCondition = '((!(ActionMatches{\'Microsoft.ContainerRegistry/registries/repositories/content/read\'}) AND !(ActionMatches{\'Microsoft.ContainerRegistry/registries/repositories/metadata/read\'})) OR (@Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase \'${repositoryName}\'))'

resource applicationRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
    roleAssignmentMode: 'AbacRepositoryPermissions'
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource imagePullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: imagePullIdentityName
  location: location
}

resource repositoryReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: applicationRegistry
  name: guid(
    applicationRegistry.id,
    imagePullIdentity.id,
    repositoryReaderRoleDefinitionId,
    repositoryName
  )
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      repositoryReaderRoleDefinitionId
    )
    principalId: imagePullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    condition: repositoryReaderCondition
    conditionVersion: '2.0'
    description: 'Container Registry Repository Reader limited to the application repository.'
  }
}

output registryId string = applicationRegistry.id
output registryLoginServer string = applicationRegistry.properties.loginServer
output imagePullIdentityId string = imagePullIdentity.id
output imagePullIdentityClientId string = imagePullIdentity.properties.clientId
output imagePullIdentityPrincipalId string = imagePullIdentity.properties.principalId
output repositoryName string = repositoryName