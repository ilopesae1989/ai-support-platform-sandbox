param vnetName string
param location string
param vnetAddressPrefix string
param containerAppsSubnetName string
param containerAppsSubnetPrefix string
param privateEndpointSubnetName string
param privateEndpointSubnetPrefix string
param privateDnsZoneName string

resource applicationVnet 'Microsoft.Network/virtualNetworks@2025-05-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
  }
}

resource containerAppsSubnet 'Microsoft.Network/virtualNetworks/subnets@2025-05-01' = {
  parent: applicationVnet
  name: containerAppsSubnetName
  properties: {
    addressPrefix: containerAppsSubnetPrefix
    delegations: [
      {
        name: 'Microsoft.App-environments'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2025-05-01' = {
  parent: applicationVnet
  name: privateEndpointSubnetName
  properties: {
    addressPrefix: privateEndpointSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource sqlPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: privateDnsZoneName
  location: 'global'
  properties: {}
}

resource sqlPrivateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: sqlPrivateDnsZone
  name: '${vnetName}-sql-dns-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: applicationVnet.id
    }
  }
}

output vnetId string = applicationVnet.id
output containerAppsSubnetId string = containerAppsSubnet.id
output privateEndpointSubnetId string = privateEndpointSubnet.id
output privateDnsZoneId string = sqlPrivateDnsZone.id