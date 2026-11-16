resource "azapi_resource" "res-1" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/72fafb9e-0641-4937-9268-a91bfd8191a3"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/72fafb9e-0641-4937-9268-a91bfd8191a3"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_6250ce61e3a8}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_6250ce61e3a8}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_52d03af37df9}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_52d03af37df9}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_4121e1e92d22}"
      principalType                      = "ForeignGroup"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_4121e1e92d22}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-5" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_febfcad5c8ab}"
      principalType                      = "Group"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_febfcad5c8ab}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_container_apps_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.ref_container_apps_res_3_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-8" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-20.id
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.ref_identities_res_3_principal_id}", azapi_resource.res-20.id]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_424f9d09392f}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_424f9d09392f}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_427d2b2256ac}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_427d2b2256ac}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-11" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/fa23ad8b-c56e-40d8-ac0c-ce449e1d2c64"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/fa23ad8b-c56e-40d8-ac0c-ce449e1d2c64"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-12" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_1da5714fc9be}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_1da5714fc9be}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-13" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_d344e786d136}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_d344e786d136}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-14" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-15" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = "Dedicated READ assignment for azure-mcp-rglist-read-sbx only."
      principalId                        = "${var.ref_container_apps_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-26.id
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.ref_container_apps_res_4_principal_id}", azapi_resource.res-26.id]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-16" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_642543bf73c0}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_642543bf73c0}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-17" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/434105ed-43f6-45c7-a02f-909b2ba83430"
    }
  }
  name      = uuidv5("url", jsonencode(["/subscriptions/${var.subscription_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/434105ed-43f6-45c7-a02f-909b2ba83430"]))
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-18" {
  body = {
    properties = {
      assignableScopes = ["${var.ref_foundation_res_7_id}"]
      description      = "Candidate for the dedicated WRITE executor only: read and start the exact assigned VM. No other power action, VM write or delete."
      permissions = [{
        actions        = ["Microsoft.Compute/virtualMachines/read", "Microsoft.Compute/virtualMachines/start/action"]
        dataActions    = []
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support Platform VM Start Exact WRITE SBX"
      type     = "CustomRole"
    }
  }
  name      = "592cb52d-28b4-5d98-964e-d09e709959db"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-19" {
  body = {
    properties = {
      assignableScopes = ["${var.ref_foundation_res_3_id}"]
      description      = "F27 receipt signer: read public key material and sign digests. Assign only to the intended receipt key; no key administration."
      permissions = [{
        actions        = []
        dataActions    = ["Microsoft.KeyVault/vaults/keys/read", "Microsoft.KeyVault/vaults/keys/sign/action"]
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support F27 Receipt Key Signer"
      type     = "CustomRole"
    }
  }
  name      = "5f53686d-d69b-493d-bc52-170a66bbb028"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-20" {
  body = {
    properties = {
      assignableScopes = ["/subscriptions/${var.subscription_id}"]
      description      = "Candidate metadata-only read of Compute asynchronous operation status in the VM subscription; grants no VM operation."
      permissions = [{
        actions        = ["Microsoft.Compute/locations/operations/read"]
        dataActions    = []
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support Platform VM Start Async Status READ SBX"
      type     = "CustomRole"
    }
  }
  name      = "7260cb9e-4a63-5501-829c-48eb6195a3a2"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-21" {
  body = {
    properties = {
      assignableScopes = ["${var.ref_foundation_res_6_id}"]
      description      = "F27 custody writer; exact container assignment; no deletion, overwrite, delegation keys or policy mutation."
      permissions = [{
        actions        = []
        dataActions    = ["Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read", "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action"]
        notActions     = []
        notDataActions = []
      }]
      roleName = "F27 Receipt Blob Creator SBX"
      type     = "CustomRole"
    }
  }
  name      = "92268fde-a634-579c-bf2a-e4e5a7558d41"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-22" {
  body = {
    properties = {
      assignableScopes = ["/subscriptions/${var.subscription_id}"]
      description      = "Read only the runtime instance view of Azure virtual machines when assigned at an explicit resource scope."
      permissions = [{
        actions        = ["Microsoft.Compute/virtualMachines/instanceView/read"]
        dataActions    = []
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support Platform VM Instance View Reader"
      type     = "CustomRole"
    }
  }
  name      = "9999ca10-f679-57ee-af24-a37ceedf59f2"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-23" {
  body = {
    properties = {
      assignableScopes = ["${var.ref_foundation_res_7_id}"]
      description      = "Candidate auxiliary metadata read for the parent RG only; no Compute permissions at RG scope."
      permissions = [{
        actions        = ["Microsoft.Resources/subscriptions/resourceGroups/read"]
        dataActions    = []
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support Platform VM Start Parent RG Metadata READ SBX"
      type     = "CustomRole"
    }
  }
  name      = "9e2f2c1b-8934-5362-b5ef-357e4cba8080"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-24" {
  body = {
    properties = {
      assignableScopes = ["/subscriptions/${var.subscription_id}"]
      description      = "F27 independent attestor: read stored Foundry project responses. No response creation, deletion, invocation or key management."
      permissions = [{
        actions        = []
        dataActions    = ["Microsoft.CognitiveServices/accounts/AIServices/responses/read"]
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support F27 Foundry Response Reader"
      type     = "CustomRole"
    }
  }
  name      = "a577e743-fa1a-4a13-b805-aa107eee2084"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-25" {
  body = {
    properties = {
      assignableScopes = ["${var.ref_foundation_res_6_id}"]
      description      = "F27 custody reader; exact container assignment; no deletion, overwrite, delegation keys or policy mutation."
      permissions = [{
        actions        = ["Microsoft.Storage/storageAccounts/blobServices/containers/immutabilityPolicies/read"]
        dataActions    = ["Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read"]
        notActions     = []
        notDataActions = []
      }]
      roleName = "F27 Receipt Blob Verifier SBX"
      type     = "CustomRole"
    }
  }
  name      = "b1c5ef43-3fc7-58b6-a8a6-d738809c08c0"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-26" {
  body = {
    properties = {
      assignableScopes = ["/subscriptions/${var.subscription_id}"]
      description      = "Dedicated resource group list READ for the new AI Support Platform sandbox Container App identity."
      permissions = [{
        actions        = ["Microsoft.Resources/subscriptions/resourceGroups/read"]
        dataActions    = []
        notActions     = []
        notDataActions = []
      }]
      roleName = "AI Support Platform RG List READ SBX 557fda"
      type     = "CustomRole"
    }
  }
  name      = "bfb9ac46-7781-4c13-889d-ff9f48ae8253"
  parent_id = "/subscriptions/${var.subscription_id}"
  type      = "Microsoft.Authorization/roleDefinitions@2022-05-01-preview"
}
resource "azapi_resource" "res-27" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundation_res_2_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"]))
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-28" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_5_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-19.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}/keys/asp-correlation-receipt-sbx", "${var.ref_identities_res_5_principal_id}", azapi_resource.res-19.id]))
  parent_id = "${var.ref_key_vault_res_1_id}/keys/asp-correlation-receipt-sbx"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-29" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_container_apps_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-19.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}/keys/asp-mcp-read-receipt-sbx", "${var.ref_container_apps_res_4_principal_id}", azapi_resource.res-19.id]))
  parent_id = "${var.ref_key_vault_res_1_id}/keys/asp-mcp-read-receipt-sbx"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-30" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-19.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}/keys/asp-mcp-write-receipt-sbx", "${var.ref_identities_res_3_principal_id}", azapi_resource.res-19.id]))
  parent_id = "${var.ref_key_vault_res_1_id}/keys/asp-mcp-write-receipt-sbx"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-31" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b86a8fe4-44ce-4948-aee5-eccb2c155cd7"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b86a8fe4-44ce-4948-aee5-eccb2c155cd7"]))
  parent_id = var.ref_key_vault_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-32" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/21090545-7ca7-4776-b22c-e363652d74d2"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/21090545-7ca7-4776-b22c-e363652d74d2"]))
  parent_id = var.ref_key_vault_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-33" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4633458b-17de-408a-b874-0445c86b69e6"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}", "${var.ref_identities_res_4_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4633458b-17de-408a-b874-0445c86b69e6"]))
  parent_id = var.ref_key_vault_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-34" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/14b46e9e-c2b7-41b4-b07b-48a6ebf60603"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_key_vault_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/14b46e9e-c2b7-41b4-b07b-48a6ebf60603"]))
  parent_id = var.ref_key_vault_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-35" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8ebe5a00-799e-43f5-93ac-243d3dce84a7"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_search_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8ebe5a00-799e-43f5-93ac-243d3dce84a7"]))
  parent_id = var.ref_search_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-36" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/7ca78c08-252a-4471-8644-bb5ff32d4ba0"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_search_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/7ca78c08-252a-4471-8644-bb5ff32d4ba0"]))
  parent_id = var.ref_search_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-37" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_storage_res_22_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe"]))
  parent_id = var.ref_storage_res_22_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-38" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundation_res_4_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"]))
  parent_id = var.ref_foundation_res_4_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-39" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = "Communication runtime can interact only with agent-communication-sbx."
      principalId                        = "${var.ref_identities_res_7_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundry_res_14_id}/agents/agent-communication-sbx", "${var.ref_identities_res_7_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/eed3b665-ab3a-47b6-8f48-c9382fb1dad6"]))
  parent_id = "${var.ref_foundry_res_14_id}/agents/agent-communication-sbx"
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-40" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_7_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundry_res_14_id}", "${var.ref_identities_res_7_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/eed3b665-ab3a-47b6-8f48-c9382fb1dad6"]))
  parent_id = var.ref_foundry_res_14_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-41" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_5_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-24.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundry_res_14_id}", "${var.ref_identities_res_5_principal_id}", azapi_resource.res-24.id]))
  parent_id = var.ref_foundry_res_14_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-42" {
  body = {
    properties = {
      condition                          = "( ( !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/read'}) AND !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/read'}) ) OR ( @Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'f27-azure-mcp-sensor' ))"
      conditionVersion                   = "2.0"
      delegatedManagedIdentityResourceId = null
      description                        = "F27 sandbox MCP image pull limited to repository f27-azure-mcp-sensor"
      principalId                        = "${var.ref_container_apps_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.ref_container_apps_res_3_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-43" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = "Phase23 sandbox ACR repository catalog access"
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/bfdb9389-c9a5-478a-bb2f-ba9ca092c3c7"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/bfdb9389-c9a5-478a-bb2f-ba9ca092c3c7"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-44" {
  body = {
    properties = {
      condition                          = "((!(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/read'}) AND !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/read'})) OR (@Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'f27-azure-mcp-sensor'))"
      conditionVersion                   = "2.0"
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.ref_identities_res_3_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-45" {
  body = {
    properties = {
      condition                          = "((!(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/read'}) AND !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/read'})) OR (@Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'ai-support-platform'))"
      conditionVersion                   = "2.0"
      delegatedManagedIdentityResourceId = null
      description                        = "Container Registry Repository Reader limited to the application repository."
      principalId                        = "${var.ref_identities_res_2_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.ref_identities_res_2_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-46" {
  body = {
    properties = {
      condition                          = "((!(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/read'}) AND !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/read'})) OR (@Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'f27-azure-mcp-sensor'))"
      conditionVersion                   = "2.0"
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_container_apps_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.ref_container_apps_res_4_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b93aa761-3e63-49ed-ac28-beffa264f7ac"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-47" {
  body = {
    properties = {
      condition                          = "(\n (\n  !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/read'})\n  AND\n  !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/read'})\n  AND\n  !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/metadata/write'})\n  AND\n  !(ActionMatches{'Microsoft.ContainerRegistry/registries/repositories/content/write'})\n )\n OR\n (\n  @Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'ai-support-platform'\n  OR\n  @Request[Microsoft.ContainerRegistry/registries/repositories:name] StringEqualsIgnoreCase 'f27-azure-mcp-sensor'\n )\n)"
      conditionVersion                   = "2.0"
      delegatedManagedIdentityResourceId = null
      description                        = "Phase23 sandbox build authority limited to repositories ai-support-platform and f27-azure-mcp-sensor"
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/2a1e307c-b015-4ebd-883e-5b7698a07328"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_registry_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/2a1e307c-b015-4ebd-883e-5b7698a07328"]))
  parent_id = var.ref_registry_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-48" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.external_00f78361ed27}"
      principalType                      = "User"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/090c5cfd-751d-490a-894a-3ce6f1109419"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_messaging_res_1_id}", "${var.external_00f78361ed27}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/090c5cfd-751d-490a-894a-3ce6f1109419"]))
  parent_id = var.ref_messaging_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-49" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_messaging_res_1_id}", "${var.ref_identities_res_4_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0"]))
  parent_id = var.ref_messaging_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-50" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_4_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/69a216fc-b8fb-44d8-bc22-1f3c2cd27a39"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_messaging_res_1_id}", "${var.ref_identities_res_4_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/69a216fc-b8fb-44d8-bc22-1f3c2cd27a39"]))
  parent_id = var.ref_messaging_res_1_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-51" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_foundry_res_14_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/73c42c96-874c-492b-b04d-ab87d138a893"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_observability_res_5_id}", "${var.ref_foundry_res_14_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/73c42c96-874c-492b-b04d-ab87d138a893"]))
  parent_id = var.ref_observability_res_5_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-52" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_foundry_res_14_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_observability_res_5_id}", "${var.ref_foundry_res_14_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7"]))
  parent_id = var.ref_observability_res_5_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-53" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_foundry_res_14_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/73c42c96-874c-492b-b04d-ab87d138a893"
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_observability_res_6_id}", "${var.ref_foundry_res_14_principal_id}", "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/73c42c96-874c-492b-b04d-ab87d138a893"]))
  parent_id = var.ref_observability_res_6_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-54" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_6_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-25.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_storage_res_35_id}", "${var.ref_identities_res_6_principal_id}", azapi_resource.res-25.id]))
  parent_id = var.ref_storage_res_35_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-55" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_5_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-21.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_storage_res_35_id}", "${var.ref_identities_res_5_principal_id}", azapi_resource.res-21.id]))
  parent_id = var.ref_storage_res_35_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-56" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-23.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_foundation_res_7_id}", "${var.ref_identities_res_3_principal_id}", azapi_resource.res-23.id]))
  parent_id = var.ref_foundation_res_7_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-57" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = null
      principalId                        = "${var.ref_identities_res_3_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-18.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_compute_res_3_id}", "${var.ref_identities_res_3_principal_id}", azapi_resource.res-18.id]))
  parent_id = var.ref_compute_res_3_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
resource "azapi_resource" "res-58" {
  body = {
    properties = {
      condition                          = null
      conditionVersion                   = null
      delegatedManagedIdentityResourceId = null
      description                        = "VM observation runtime can read only the instance view of vm-icenter-sbx-demo-01."
      principalId                        = "${var.ref_identities_res_10_principal_id}"
      principalType                      = "ServicePrincipal"
      roleDefinitionId                   = azapi_resource.res-22.id
    }
  }
  name      = uuidv5("url", jsonencode(["${var.ref_compute_res_3_id}", "${var.ref_identities_res_10_principal_id}", azapi_resource.res-22.id]))
  parent_id = var.ref_compute_res_3_id
  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"
}
