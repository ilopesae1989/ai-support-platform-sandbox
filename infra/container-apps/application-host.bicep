param environmentName string
param containerAppName string
param location string
param infrastructureSubnetId string
param imageByDigest string
param registryServer string
param imagePullIdentityResourceId string
param teamsIdentityResourceId string
param azureSqlIdentityResourceId string
param azureVmReaderIdentityResourceId string
param foundryIdentityResourceId string
param containerCpu string
param containerMemory string
param clientId string
param teamsManagedIdentityClientId string
param tenantId string
param teamsChannelTenantId string
param teamsAuthorizedTechniciansGroupObjectId string
param azureSqlServer string
param azureSqlDatabase string
param azureSqlManagedIdentityClientId string
param foundryProjectEndpoint string
param foundryManagedIdentityClientId string
param azureVmReaderManagedIdentityClientId string

resource applicationEnvironment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: environmentName
  location: location
  properties: {
    publicNetworkAccess: 'Enabled'
    vnetConfiguration: {
      infrastructureSubnetId: infrastructureSubnetId
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource applicationHost 'Microsoft.App/containerApps@2026-01-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${imagePullIdentityResourceId}': {}
      '${teamsIdentityResourceId}': {}
      '${azureSqlIdentityResourceId}': {}
      '${azureVmReaderIdentityResourceId}': {}
      '${foundryIdentityResourceId}': {}
    }
  }
  properties: {
    environmentId: applicationEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: registryServer
          identity: imagePullIdentityResourceId
        }
      ]
      identitySettings: [
        {
          identity: imagePullIdentityResourceId
          lifecycle: 'None'
        }
        {
          identity: teamsIdentityResourceId
          lifecycle: 'Main'
        }
        {
          identity: azureSqlIdentityResourceId
          lifecycle: 'Main'
        }
        {
          identity: azureVmReaderIdentityResourceId
          lifecycle: 'Main'
        }
        {
          identity: foundryIdentityResourceId
          lifecycle: 'Main'
        }
      ]
      ingress: {
        external: true
        targetPort: 3978
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'application'
          image: imageByDigest
          env: [
            {
              name: 'CLIENT_ID'
              value: clientId
            }
            {
              name: 'MANAGED_IDENTITY_CLIENT_ID'
              value: teamsManagedIdentityClientId
            }
            {
              name: 'TENANT_ID'
              value: tenantId
            }
            {
              name: 'TEAMS_CHANNEL_TENANT_ID'
              value: teamsChannelTenantId
            }
            {
              name: 'TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID'
              value: teamsAuthorizedTechniciansGroupObjectId
            }
            {
              name: 'AZURE_SQL_SERVER'
              value: azureSqlServer
            }
            {
              name: 'AZURE_SQL_DATABASE'
              value: azureSqlDatabase
            }
            {
              name: 'AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID'
              value: azureSqlManagedIdentityClientId
            }
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_MANAGED_IDENTITY_CLIENT_ID'
              value: foundryManagedIdentityClientId
            }
            {
              name: 'AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID'
              value: azureVmReaderManagedIdentityClientId
            }
          ]
          resources: {
            cpu: json(containerCpu)
            memory: containerMemory
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output environmentId string = applicationEnvironment.id
output containerAppId string = applicationHost.id
output containerAppFqdn string = applicationHost.properties.configuration.ingress.fqdn