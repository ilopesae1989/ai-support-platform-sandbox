targetScope = 'subscription'

@description('Existing/custom role definition GUID.')
param roleDefinitionId string

@description('Resource Group ID where the custom role can be assigned.')
param assignableResourceGroupId string

@description('Custom role display name.')
param roleName string = 'AI Support POC VM Start Operator'

@description('Custom role description.')
param roleDescription string = 'Allows AI Support POC MCP identity to start the approved sandbox VM.'

resource vmStartRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: roleDefinitionId
  properties: {
    roleName: roleName
    description: roleDescription
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.Compute/virtualMachines/start/action'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: [
      assignableResourceGroupId
    ]
  }
}

output roleDefinitionResourceId string = vmStartRole.id
output roleDefinitionName string = vmStartRole.name
