targetScope = 'resourceGroup'

@description('Exact Azure VM resource ID authorized for VM start.')
param targetVmResourceId string

@description('Azure Container App managed identity principal/object ID.')
param acaPrincipalId string

@description('Full custom role definition resource ID.')
param roleDefinitionResourceId string

@description('Existing role assignment GUID to adopt. Empty creates a deterministic name.')
param roleAssignmentName string = ''

var targetVmParts = split(
  targetVmResourceId,
  '/'
)

var targetVmIdLower = toLower(
  targetVmResourceId
)

var targetVmHasCorrectSegmentCount = length(targetVmParts) == 9

var targetVmStartsWithSubscriptions = startsWith(
  targetVmIdLower,
  '/subscriptions/'
)

var targetVmHasComputeProvider = contains(
  targetVmIdLower,
  '/providers/microsoft.compute/virtualmachines/'
)

var targetVmSubscriptionMatches = toLower(targetVmParts[2]) == toLower(subscription().subscriptionId)

var targetVmResourceGroupMatches = toLower(targetVmParts[4]) == toLower(resourceGroup().name)

var validTargetVm = targetVmHasCorrectSegmentCount && targetVmStartsWithSubscriptions && targetVmHasComputeProvider && targetVmSubscriptionMatches && targetVmResourceGroupMatches

var validatedTargetVmResourceId = validTargetVm
  ? targetVmResourceId
  : fail('targetVmResourceId must identify a virtual machine in the current subscription and resource group.')

var validatedTargetVmParts = split(
  validatedTargetVmResourceId,
  '/'
)

var targetVmName = validatedTargetVmParts[8]

resource targetVm 'Microsoft.Compute/virtualMachines@2024-11-01' existing = {
  name: targetVmName
}

var effectiveRoleAssignmentName = empty(roleAssignmentName)
  ? guid(
      targetVm.id,
      acaPrincipalId,
      roleDefinitionResourceId
    )
  : roleAssignmentName

resource vmStartRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: effectiveRoleAssignmentName
  scope: targetVm
  properties: {
    roleDefinitionId: roleDefinitionResourceId
    principalId: acaPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output roleAssignmentId string = vmStartRoleAssignment.id
output roleAssignmentName string = vmStartRoleAssignment.name
