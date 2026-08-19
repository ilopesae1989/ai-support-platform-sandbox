@description('Location for all resources')
param location string = resourceGroup().location

@description('Name for the Azure Container App')
param acaName string

@description('Display name for the Entra App')
param entraAppDisplayName string

@description('Full resource ID of the exact Azure VM that Azure MCP is allowed to start')
param targetVmResourceId string

@description('Existing custom role definition GUID for the governed VM start capability')
param vmStartRoleDefinitionId string

@description('Existing subscription Reader role assignment GUID to adopt. Leave empty for a new environment.')
param readerRoleAssignmentName string = ''

@description('Existing VM Start role assignment GUID to adopt. Leave empty for a new environment.')
param vmStartRoleAssignmentName string = ''

@description('Microsoft Foundry project resource ID for assigning Entra App role to Foundry project managed identity')
param foundryProjectResourceId string

@description('Service Management Reference for the Entra Application. Optional GUID used to link the app to a service in Azure.')
param serviceManagementReference string = ''

@description('Application Insights connection string. Use "DISABLED" to disable telemetry, or provide existing connection string. If omitted, new App Insights will be created.')
param appInsightsConnectionString string = ''

// Validate targetVmResourceId format.
// Expected:
// /subscriptions/{sub}/resourceGroups/{rg}/providers/
// Microsoft.Compute/virtualMachines/{vm}
var targetVmIdLower = toLower(targetVmResourceId)
var targetVmParts = split(targetVmResourceId, '/')

var targetVmHasCorrectSegmentCount = length(targetVmParts) == 9
var targetVmStartsWithSubscriptions = startsWith(
  targetVmIdLower,
  '/subscriptions/'
)
var targetVmHasProvider = contains(
  targetVmIdLower,
  '/providers/microsoft.compute/virtualmachines/'
)
var targetVmSubscriptionMatches = toLower(targetVmParts[2]) == toLower(subscription().subscriptionId)

var isValidTargetVmResourceId = targetVmHasCorrectSegmentCount && targetVmStartsWithSubscriptions && targetVmHasProvider && targetVmSubscriptionMatches

var validatedTargetVmResourceId = isValidTargetVmResourceId
  ? targetVmResourceId
  : fail('targetVmResourceId must identify a virtual machine in the current subscription.')

var validatedTargetVmParts = split(
  validatedTargetVmResourceId,
  '/'
)

var targetVmResourceGroupName = validatedTargetVmParts[4]

var targetVmResourceGroupId = '/subscriptions/${subscription().subscriptionId}/resourceGroups/${targetVmResourceGroupName}'

// Validate foundryProjectResourceId format
// Expected: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}
var foundryIdLower = toLower(foundryProjectResourceId)
var hasCorrectSegmentCount = length(split(foundryProjectResourceId, '/')) == 11
var startsWithSubscriptions = startsWith(foundryIdLower, '/subscriptions/')
var hasCognitiveServicesProvider = contains(foundryIdLower, '/providers/microsoft.cognitiveservices/accounts/')
var hasProjectsSegment = contains(foundryIdLower, '/projects/')
var isValidFoundryProjectResourceId = hasCorrectSegmentCount && startsWithSubscriptions && hasCognitiveServicesProvider && hasProjectsSegment

// Expected format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}
var validatedFoundryProjectResourceId = isValidFoundryProjectResourceId
  ? foundryProjectResourceId
  : fail('foundryProjectResourceId does not match the required Microsoft Foundry project resource ID format.')

// Deploy Application Insights if appInsightsConnectionString is empty and not DISABLED
var appInsightsName = '${acaName}-insights'
//
module appInsights 'modules/application-insights.bicep' = {
  name: 'application-insights-deployment'
  params: {
    appInsightsConnectionString: appInsightsConnectionString
    name: appInsightsName
    location: location
  }
}

// Deploy Entra App
var entraAppUniqueName = '${replace(toLower(entraAppDisplayName), ' ', '-')}-${uniqueString(resourceGroup().id)}'
//
module entraApp 'modules/entra-app.bicep' = {
  name: 'entra-app-deployment'
  params: {
    entraAppDisplayName: entraAppDisplayName
    entraAppUniqueName: entraAppUniqueName
    serviceManagementReference: serviceManagementReference
  }
}

// Deploy ACA Infrastructure to host Azure MCP Server
module acaInfrastructure 'modules/aca-infrastructure.bicep' = {
  name: 'aca-infrastructure-deployment'
  params: {
    name: acaName
    location: location
    appInsightsConnectionString: appInsights.outputs.connectionString
    azureMcpCollectTelemetry: string(!empty(appInsights.outputs.connectionString))
    azureAdTenantId: tenant().tenantId
    azureAdClientId: entraApp.outputs.entraAppClientId
    tools: [
      'subscription_list'
      'group_list'
      'group_resource_list'
      'advisor_recommendation_list'
      'advisor_recommendation_summary'
      'compute_vm-power-state'
    ]
  }
}

// Governed Azure MCP RBAC.
//
// READ:
// Reader at subscription scope supports the certified
// subscription/resource-group/Advisor read tools.
//
// WRITE:
// A custom role contains exactly VM start/action and can
// be assigned only within the approved VM Resource Group.
// The role assignment itself is scoped to targetVmResourceId.
module vmStartRoleDefinition 'modules/vm-start-role-definition.bicep' = {
  name: 'vm-start-role-definition-deployment'
  scope: subscription()
  params: {
    roleDefinitionId: vmStartRoleDefinitionId
    assignableResourceGroupId: targetVmResourceGroupId
  }
}

module acaSubscriptionReader 'modules/aca-subscription-reader-role-assignment.bicep' = {
  name: 'aca-subscription-reader-role-assignment'
  scope: subscription()
  params: {
    acaPrincipalId: acaInfrastructure.outputs.containerAppPrincipalId
    roleAssignmentName: readerRoleAssignmentName
  }
}

module acaVmStartRoleAssignment 'modules/aca-vm-start-role-assignment.bicep' = {
  name: 'aca-vm-start-role-assignment'
  scope: resourceGroup(targetVmResourceGroupName)
  params: {
    targetVmResourceId: validatedTargetVmResourceId
    acaPrincipalId: acaInfrastructure.outputs.containerAppPrincipalId
    roleDefinitionResourceId: vmStartRoleDefinition.outputs.roleDefinitionResourceId
    roleAssignmentName: vmStartRoleAssignmentName
  }
}

// Deploy Entra App role assignment for Microsoft Foundry project MI to access ACA
module foundryRoleAssignment './modules/foundry-role-assignment-entraapp.bicep' = {
  name: 'foundry-role-assignment'
  params: {
    foundryProjectResourceId: validatedFoundryProjectResourceId
    entraAppServicePrincipalObjectId: entraApp.outputs.entraAppServicePrincipalObjectId
    entraAppRoleId: entraApp.outputs.entraAppRoleId
  }
}

// Outputs for azd and other consumers
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_LOCATION string = location

// Entra App outputs
output ENTRA_APP_CLIENT_ID string = entraApp.outputs.entraAppClientId
output ENTRA_APP_OBJECT_ID string = entraApp.outputs.entraAppObjectId
output ENTRA_APP_SERVICE_PRINCIPAL_ID string = entraApp.outputs.entraAppServicePrincipalObjectId
output ENTRA_APP_ROLE_ID string = entraApp.outputs.entraAppRoleId
output ENTRA_APP_IDENTIFIER_URI string = entraApp.outputs.entraAppIdentifierUri

// ACA Infrastructure outputs
output CONTAINER_APP_URL string = acaInfrastructure.outputs.containerAppUrl
output CONTAINER_APP_NAME string = acaInfrastructure.outputs.containerAppName
output CONTAINER_APP_PRINCIPAL_ID string = acaInfrastructure.outputs.containerAppPrincipalId

// Governed Azure MCP RBAC outputs
output VM_START_ROLE_DEFINITION_ID string = vmStartRoleDefinition.outputs.roleDefinitionResourceId
output READER_ROLE_ASSIGNMENT_ID string = acaSubscriptionReader.outputs.roleAssignmentId
output VM_START_ROLE_ASSIGNMENT_ID string = acaVmStartRoleAssignment.outputs.roleAssignmentId
output AZURE_CONTAINER_APP_ENVIRONMENT_ID string = acaInfrastructure.outputs.containerAppEnvironmentId

// Application Insights outputs
output APPLICATION_INSIGHTS_NAME string = appInsightsName
output APPLICATION_INSIGHTS_CONNECTION_STRING string = appInsights.outputs.connectionString
output AZURE_MCP_COLLECT_TELEMETRY string = string(!empty(appInsights.outputs.connectionString))
