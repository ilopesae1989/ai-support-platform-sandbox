resource "azapi_resource" "res-1" {
  response_export_values = ["properties.configuration.ingress.fqdn"]
  body = {
    properties = {
      configuration = {
        activeRevisionsMode = "Single"
        dapr                = null
        identitySettings = [{
          identity  = "${var.ref_identities_res_2_id}"
          lifecycle = "None"
          }, {
          identity  = "${var.ref_identities_res_9_id}"
          lifecycle = "Main"
          }, {
          identity  = "${var.ref_identities_res_1_id}"
          lifecycle = "Main"
          }, {
          identity  = "${var.ref_identities_res_10_id}"
          lifecycle = "Main"
          }, {
          identity  = "${var.ref_identities_res_7_id}"
          lifecycle = "Main"
        }]
        ingress = {
          additionalPortMappings = null
          allowInsecure          = false
          clientCertificateMode  = null
          corsPolicy             = null
          customDomains          = null
          exposedPort            = 0
          external               = true
          ipSecurityRestrictions = null
          stickySessions         = null
          targetPort             = 3978
          targetPortHttpScheme   = null
          traffic = [{
            latestRevision = true
            weight         = 100
          }]
          transport = "Auto"
        }
        maxInactiveRevisions = 100
        registries = [{
          identity          = "${var.ref_identities_res_2_id}"
          passwordSecretRef = ""
          server            = "${var.ref_registry_res_1_login_server}"
          username          = ""
        }]
        revisionTransitionThreshold = null
        runtime                     = null
        secrets                     = var.secret_container_apps_res_1_secrets
        service                     = null
        targetLabel                 = ""
      }
      environmentId        = azapi_resource.res-2.id
      managedEnvironmentId = azapi_resource.res-2.id
      template = {
        containers = [{
          env = [{
            name  = "CLIENT_ID"
            value = "${var.external_15e21363cbc3}"
            }, {
            name  = "MANAGED_IDENTITY_CLIENT_ID"
            value = "${var.ref_identities_res_9_client_id}"
            }, {
            name  = "TENANT_ID"
            value = "${var.tenant_id}"
            }, {
            name  = "TEAMS_CHANNEL_TENANT_ID"
            value = var.teams_channel_tenant_id
            }, {
            name  = "TEAMS_AUTHORIZATION_DIRECTORY_TENANT_ID"
            value = "${var.tenant_id}"
            }, {
            name  = "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
            value = var.teams_authorization_identity_mappings_json
            }, {
            name  = "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID"
            value = var.teams_authorized_technicians_group_object_id
            }, {
            name  = "AZURE_SQL_SERVER"
            value = "sql-icenter-app-sbx-eus2-557fda.database.windows.net"
            }, {
            name  = "AZURE_SQL_DATABASE"
            value = "sqldb-ai-support-platform-sbx"
            }, {
            name  = "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
            value = "${var.ref_identities_res_1_client_id}"
            }, {
            name  = "FOUNDRY_PROJECT_ENDPOINT"
            value = "https://aif-icenter-sbx-eus2.services.ai.azure.com/api/projects/aifproj-icenter-sbx"
            }, {
            name  = "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID"
            value = "${var.ref_identities_res_7_client_id}"
            }, {
            name  = "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID"
            value = "${var.ref_identities_res_10_client_id}"
          }]
          image     = "${var.ref_registry_res_1_login_server}/ai-support-platform@sha256:7160ff086cd452235879a04bdae53f7d312e94b17ecc3421dd1501a432b9a65a"
          imageType = "ContainerImage"
          name      = "application"
          resources = {
            cpu    = 0.5
            memory = "1Gi"
          }
        }]
        initContainers = null
        revisionSuffix = "r24-review-2821e18"
        scale = {
          cooldownPeriod  = 300
          maxReplicas     = 1
          minReplicas     = 1
          pollingInterval = 30
          rules           = null
        }
        serviceBinds                  = null
        terminationGracePeriodSeconds = null
        volumes                       = null
      }
      workloadProfileName = "Consumption"
    }
  }
  location  = "northeurope"
  name      = "ca-app-runtime-icenter-sbx"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.App/containerapps@2025-10-02-preview"
  identity {
    identity_ids = ["${var.ref_identities_res_9_id}", "${var.ref_identities_res_1_id}", "${var.ref_identities_res_10_id}", "${var.ref_identities_res_7_id}", "${var.ref_identities_res_2_id}"]
    type         = "UserAssigned"
  }
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      appInsightsConfiguration = null
      appLogsConfiguration = {
        destination               = null
        logAnalyticsConfiguration = null
      }
      availabilityZones = null
      customDomainConfiguration = {
        certificateKeyVaultProperties = null
        certificatePassword           = null
        certificateValue              = null
        dnsSuffix                     = null
      }
      daprAIConnectionString      = null
      daprAIInstrumentationKey    = null
      daprConfiguration           = {}
      diskEncryptionConfiguration = null
      infrastructureResourceGroup = "ME_cae-app-runtime-icenter-sbx_rg-icenter-sandbox-application_northeurope"
      ingressConfiguration        = null
      kedaConfiguration           = {}
      openTelemetryConfiguration  = null
      peerAuthentication = {
        mtls = {
          enabled = false
        }
      }
      peerTrafficConfiguration = {
        encryption = {
          enabled = false
        }
      }
      publicNetworkAccess = "Enabled"
      vnetConfiguration = {
        dockerBridgeCidr       = null
        infrastructureSubnetId = "${var.ref_network_res_9_id}/subnets/snet-containerapps-runtime"
        internal               = false
        platformReservedCidr   = null
        platformReservedDnsIP  = null
      }
      workloadProfiles = [{
        enableFips          = false
        name                = "Consumption"
        workloadProfileType = "Consumption"
      }]
      zoneRedundant = false
    }
  }
  location  = "northeurope"
  name      = "cae-app-runtime-icenter-sbx"
  parent_id = var.ref_foundation_res_2_id
  type      = "Microsoft.App/managedEnvironments@2025-10-02-preview"
}
resource "azapi_resource" "res-3" {
  response_export_values = ["identity.principalId", "properties.configuration.ingress.fqdn"]
  body = {
    properties = {
      configuration = {
        activeRevisionsMode = "Single"
        dapr                = null
        identitySettings    = []
        ingress = {
          additionalPortMappings = null
          allowInsecure          = false
          clientCertificateMode  = null
          corsPolicy             = null
          customDomains          = null
          exposedPort            = 0
          external               = true
          ipSecurityRestrictions = null
          stickySessions         = null
          targetPort             = 8080
          targetPortHttpScheme   = null
          traffic = [{
            latestRevision = true
            weight         = 100
          }]
          transport = "Http"
        }
        maxInactiveRevisions = null
        registries = [{
          identity          = "system"
          passwordSecretRef = ""
          server            = "${var.ref_registry_res_1_login_server}"
          username          = ""
        }]
        revisionTransitionThreshold = null
        runtime                     = null
        secrets                     = var.secret_container_apps_res_3_secrets
        service                     = null
        targetLabel                 = ""
      }
      environmentId        = azapi_resource.res-7.id
      managedEnvironmentId = azapi_resource.res-7.id
      template = {
        containers = [{
          args    = ["--transport", "http", "--outgoing-auth-strategy", "UseHostingEnvironmentIdentity", "--dangerously-disable-elicitation", "--tool", "subscription_list", "--tool", "group_list", "--tool", "group_resource_list", "--tool", "advisor_recommendation_list", "--tool", "advisor_recommendation_summary", "--tool", "compute_vm_power-state"]
          command = []
          env = [{
            name  = "ASPNETCORE_ENVIRONMENT"
            value = "Production"
            }, {
            name  = "ASPNETCORE_URLS"
            value = "http://+:8080"
            }, {
            name  = "AZURE_TOKEN_CREDENTIALS"
            value = "managedidentitycredential"
            }, {
            name  = "AZURE_MCP_INCLUDE_PRODUCTION_CREDENTIALS"
            value = "true"
            }, {
            name  = "AZURE_MCP_COLLECT_TELEMETRY"
            value = "False"
            }, {
            name  = "AzureAd__Instance"
            value = "https://login.microsoftonline.com/"
            }, {
            name  = "AzureAd__TenantId"
            value = "${var.tenant_id}"
            }, {
            name  = "AzureAd__ClientId"
            value = var.mcp_legacy_application_client_id
            }, {
            name  = "AZURE_LOG_LEVEL"
            value = "Verbose"
            }, {
            name  = "AZURE_MCP_DANGEROUSLY_DISABLE_HTTPS_REDIRECTION"
            value = "true"
            }, {
            name  = "AZURE_MCP_DANGEROUSLY_ENABLE_FORWARDED_HEADERS"
            value = "true"
            }, {
            name  = "F27_GROUP_LIST_RAW_EXPORT_PATH"
            value = "/tmp/f27-group-list-raw-export.jsonl"
          }]
          image     = "${var.ref_registry_res_1_login_server}/f27-azure-mcp-sensor@sha256:ee478bc47ef4576336a109ee1cc25ea56578e59a3c1ba7a7b6b67d9e117aafb5"
          imageType = "ContainerImage"
          name      = "azure-mcp-operations-server"
          resources = {
            cpu    = 0.25
            memory = "0.5Gi"
          }
        }]
        initContainers = null
        revisionSuffix = ""
        scale = {
          cooldownPeriod  = 300
          maxReplicas     = 3
          minReplicas     = 1
          pollingInterval = 30
          rules = [{
            http = {
              metadata = {
                concurrentRequests = "100"
              }
            }
            name = "http-scaler"
          }]
        }
        serviceBinds                  = null
        terminationGracePeriodSeconds = null
        volumes                       = null
      }
      workloadProfileName = null
    }
  }
  location  = "northeurope"
  name      = "azure-mcp-operations-server"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    product = "azmcp"
  }
  type = "Microsoft.App/containerapps@2025-10-02-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-4" {
  response_export_values = ["identity.principalId", "properties.configuration.ingress.fqdn"]
  body = {
    properties = {
      configuration = {
        activeRevisionsMode = "Multiple"
        dapr                = null
        identitySettings    = []
        ingress = {
          additionalPortMappings = null
          allowInsecure          = false
          clientCertificateMode  = null
          corsPolicy             = null
          customDomains          = null
          exposedPort            = 0
          external               = true
          ipSecurityRestrictions = null
          stickySessions         = null
          targetPort             = 8080
          targetPortHttpScheme   = null
          traffic = [{
            revisionName = "azure-mcp-rglist-read-sbx--ktcrkgt"
            weight       = 100
          }]
          transport = "Http"
        }
        maxInactiveRevisions = 100
        registries = [{
          identity          = "system"
          passwordSecretRef = ""
          server            = "${var.ref_registry_res_1_login_server}"
          username          = ""
        }]
        revisionTransitionThreshold = null
        runtime                     = null
        secrets                     = var.secret_container_apps_res_4_secrets
        service                     = null
        targetLabel                 = ""
      }
      environmentId        = azapi_resource.res-7.id
      managedEnvironmentId = azapi_resource.res-7.id
      template = {
        containers = [{
          args    = ["--transport", "http", "--outgoing-auth-strategy", "UseHostingEnvironmentIdentity", "--read-only", "--tool", "group_list"]
          command = ["/mcp-server/azmcp", "server", "start"]
          env = [{
            name  = "ASPNETCORE_ENVIRONMENT"
            value = "Production"
            }, {
            name  = "ASPNETCORE_URLS"
            value = "http://+:8080"
            }, {
            name  = "AZURE_TOKEN_CREDENTIALS"
            value = "managedidentitycredential"
            }, {
            name  = "AzureAd__Instance"
            value = "https://login.microsoftonline.com/"
            }, {
            name  = "AzureAd__TenantId"
            value = "${var.tenant_id}"
            }, {
            name  = "AzureAd__ClientId"
            value = var.mcp_read_application_client_id
            }, {
            name  = "AZURE_MCP_DANGEROUSLY_DISABLE_HTTPS_REDIRECTION"
            value = "true"
            }, {
            name  = "F27_RECEIPTS_ENABLED"
            value = "false"
          }]
          image     = "${var.ref_registry_res_1_login_server}/f27-azure-mcp-sensor@sha256:8174428a3c17e7acc1014be91188d3c78f2a7980c9c7f1f006dbb31f2b07cfd6"
          imageType = "ContainerImage"
          name      = "azure-mcp-rglist-read-sbx"
          resources = {
            cpu    = 0.25
            memory = "0.5Gi"
          }
        }]
        initContainers = null
        revisionSuffix = "f27-u187-8174428a"
        scale = {
          cooldownPeriod  = 300
          maxReplicas     = 1
          minReplicas     = 1
          pollingInterval = 30
          rules           = null
        }
        serviceBinds                  = null
        terminationGracePeriodSeconds = null
        volumes                       = null
      }
      workloadProfileName = null
    }
  }
  location  = "northeurope"
  name      = "azure-mcp-rglist-read-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    product = "ai-support-platform"
    purpose = "f27-h06-read-only"
  }
  type = "Microsoft.App/containerapps@2025-10-02-preview"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azapi_resource" "res-5" {
  response_export_values = ["properties.configuration.ingress.fqdn"]
  body = {
    properties = {
      configuration = {
        activeRevisionsMode = "Single"
        dapr                = null
        identitySettings    = []
        ingress = {
          additionalPortMappings = null
          allowInsecure          = false
          clientCertificateMode  = null
          corsPolicy             = null
          customDomains          = null
          exposedPort            = 0
          external               = true
          ipSecurityRestrictions = null
          stickySessions         = null
          targetPort             = 8080
          targetPortHttpScheme   = null
          traffic = [{
            latestRevision = true
            weight         = 100
          }]
          transport = "Http"
        }
        maxInactiveRevisions        = 100
        registries                  = null
        revisionTransitionThreshold = null
        runtime                     = null
        secrets                     = var.secret_container_apps_res_5_secrets
        service                     = null
        targetLabel                 = ""
      }
      environmentId        = azapi_resource.res-7.id
      managedEnvironmentId = azapi_resource.res-7.id
      template = {
        containers = [{
          args    = ["--transport", "http", "--outgoing-auth-strategy", "UseHostingEnvironmentIdentity", "--tool", "compute_vm_power-state"]
          command = []
          env = [{
            name  = "ASPNETCORE_ENVIRONMENT"
            value = "Production"
            }, {
            name  = "ASPNETCORE_URLS"
            value = "http://+:8080"
            }, {
            name  = "AZURE_TOKEN_CREDENTIALS"
            value = "ManagedIdentityCredential"
            }, {
            name  = "AZURE_CLIENT_ID"
            value = "${var.ref_identities_res_3_client_id}"
            }, {
            name  = "AzureAd__Instance"
            value = "https://login.microsoftonline.com/"
            }, {
            name  = "AzureAd__TenantId"
            value = "${var.tenant_id}"
            }, {
            name  = "AzureAd__ClientId"
            value = "${var.external_89b57f13a066}"
            }, {
            name  = "AZURE_MCP_DANGEROUSLY_DISABLE_HTTPS_REDIRECTION"
            value = "true"
          }]
          image     = "mcr.microsoft.com/azure-sdk/azure-mcp@sha256:2c4387a13a925b38a2592bca1f16d7d13c377332419b2db020697138ccc41268"
          imageType = "ContainerImage"
          name      = "azure-mcp-vmstart-write-sbx"
          resources = {
            cpu    = 0.25
            memory = "0.5Gi"
          }
        }]
        initContainers = null
        revisionSuffix = ""
        scale = {
          cooldownPeriod  = 300
          maxReplicas     = 1
          minReplicas     = 1
          pollingInterval = 30
          rules           = null
        }
        serviceBinds                  = null
        terminationGracePeriodSeconds = null
        volumes                       = null
      }
      workloadProfileName = null
    }
  }
  location  = "northeurope"
  name      = "azure-mcp-vmstart-write-sbx"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    product = "ai-support-platform"
    purpose = "f27-vmstart-write-candidate"
  }
  type = "Microsoft.App/containerapps@2025-10-02-preview"
  identity {
    identity_ids = ["${var.ref_identities_res_3_id}"]
    type         = "UserAssigned"
  }
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {
      encryptionSettings = {}
      globalValidation = {
        excludedPaths               = []
        unauthenticatedClientAction = "Return401"
      }
      httpSettings = {
        requireHttps = true
      }
      identityProviders = {
        azureActiveDirectory = {
          enabled           = true
          isAutoProvisioned = false
          registration = {
            clientId     = "${var.external_89b57f13a066}"
            openIdIssuer = "https://login.microsoftonline.com/0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/v2.0"
          }
          validation = {
            allowedAudiences = ["api://${var.external_89b57f13a066}"]
            defaultAuthorizationPolicy = {
              allowedPrincipals = {
                identities = ["cd53965c-2aac-4a2a-a980-814aede2b93f"]
              }
            }
          }
        }
      }
      platform = {
        enabled = true
      }
    }
  }
  name      = "current"
  parent_id = azapi_resource.res-5.id
  type      = "Microsoft.App/containerApps/authConfigs@2025-10-02-preview"
  depends_on = [
    azapi_resource.res-5,
  ]
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      appInsightsConfiguration = null
      appLogsConfiguration = {
        destination               = "azure-monitor"
        logAnalyticsConfiguration = null
      }
      availabilityZones = null
      customDomainConfiguration = {
        certificateKeyVaultProperties = null
        certificatePassword           = null
        certificateValue              = null
        dnsSuffix                     = null
      }
      daprAIConnectionString      = null
      daprAIInstrumentationKey    = null
      daprConfiguration           = {}
      diskEncryptionConfiguration = null
      infrastructureResourceGroup = null
      ingressConfiguration        = null
      kedaConfiguration           = {}
      openTelemetryConfiguration  = null
      peerAuthentication = {
        mtls = {
          enabled = false
        }
      }
      peerTrafficConfiguration = {
        encryption = {
          enabled = false
        }
      }
      publicNetworkAccess = "Enabled"
      vnetConfiguration   = null
      workloadProfiles    = null
      zoneRedundant       = false
    }
  }
  location  = "northeurope"
  name      = "azure-mcp-operations-server-env"
  parent_id = var.ref_foundation_res_5_id
  type      = "Microsoft.App/managedEnvironments@2025-10-02-preview"
}
