// Deployment candidate. Creates the independent job, never starts it or enables keys.
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentId string
param attestorIdentityResourceId string
param custodyReaderIdentityResourceId string
param registryPullIdentityResourceId string
param attestorClientId string
param imageDigestReference string
param registryServer string
param runtimeConfigurationSha256 string
param jobName string = 'job-f27-correlation-attestor-sbx'

resource attestor 'Microsoft.App/jobs@2025-07-01' = {
  name: jobName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${attestorIdentityResourceId}': {}
      '${custodyReaderIdentityResourceId}': {}
      '${registryPullIdentityResourceId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registryServer, identity: registryPullIdentityResourceId }]
    }
    template: {
      containers: [{
        name: 'attestor'
        image: imageDigestReference
        command: ['python', '-m', 'src.attestation.worker_entrypoint']
        // No operation is authorized by deployment; execution must supply its exact outbox hash.
        args: ['--help']
        env: [
          { name: 'AZURE_CLIENT_ID', value: attestorClientId }
          { name: 'F27_ATTESTATION_ENABLED', value: 'true' }
          { name: 'F27_ATTESTATION_CONFIG_PATH', value: '/app/f27/runtime.json' }
          { name: 'F27_ATTESTATION_CONFIG_SHA256', value: runtimeConfigurationSha256 }
        ]
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
}

output jobResourceId string = attestor.id
