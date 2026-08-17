targetScope = 'subscription'

@description('Azure Container App managed identity principal/object ID.')
param acaPrincipalId string

@description('Existing role assignment GUID to adopt. Empty creates a deterministic name.')
param roleAssignmentName string = ''

var readerRoleDefinitionGuid = 'acdd72a7-3385-48ef-bd42-f606fba81ae7'

var readerRoleDefinitionResourceId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  readerRoleDefinitionGuid
)

var effectiveRoleAssignmentName = empty(roleAssignmentName)
  ? guid(
      subscription().id,
      acaPrincipalId,
      readerRoleDefinitionResourceId
    )
  : roleAssignmentName

resource readerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: effectiveRoleAssignmentName
  properties: {
    roleDefinitionId: readerRoleDefinitionResourceId
    principalId: acaPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output roleAssignmentId string = readerRoleAssignment.id
output roleAssignmentName string = readerRoleAssignment.name
