resource "azapi_resource" "res-1" {
  body = {
    properties = {
      disableLocalAuth = false
      geoDataReplication = {
        locations = [{
          locationName = "northeurope"
          roleType     = "Primary"
        }]
        maxReplicationLagDurationInSeconds = 0
      }
      minimumTlsVersion = "1.2"
      platformCapabilities = {
        confidentialCompute = {
          mode = "Disabled"
        }
      }
      premiumMessagingPartitions = 0
      publicNetworkAccess        = "Enabled"
      zoneRedundant              = true
    }
    sku = {
      name = "Standard"
      tier = "Standard"
    }
  }
  location  = "northeurope"
  name      = "sb-icenter-sbx-neu"
  parent_id = var.ref_foundation_res_5_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
    workload    = "integration"
  }
  type = "Microsoft.ServiceBus/namespaces@2025-05-01-preview"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = true
      status                              = "Active"
    }
  }
  name      = "action-executions"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = true
      status                              = "Active"
    }
  }
  name      = "approval-events"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-4" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = false
      status                              = "Active"
    }
  }
  name      = "external-outbox"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-5" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P1D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = false
      status                              = "Active"
    }
  }
  name      = "queue-alerts-normalized"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-6" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = false
      status                              = "Active"
    }
  }
  name      = "rag-ingestion"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-7" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      deadLetteringOnMessageExpiration    = true
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      lockDuration                        = "PT1M"
      maxDeliveryCount                    = 10
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      requiresSession                     = true
      status                              = "Active"
    }
  }
  name      = "workflow-commands"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/queues@2025-05-01-preview"
}
resource "azapi_resource" "res-8" {
  body = {
    properties = {
      autoDeleteOnIdle                    = "P10675199DT2H48M5.4775807S"
      defaultMessageTimeToLive            = "P7D"
      duplicateDetectionHistoryTimeWindow = "PT10M"
      enableBatchedOperations             = true
      enableExpress                       = false
      enablePartitioning                  = false
      maxMessageSizeInKilobytes           = 256
      maxSizeInMegabytes                  = 1024
      requiresDuplicateDetection          = true
      status                              = "Active"
      supportOrdering                     = true
    }
  }
  name      = "domain-events"
  parent_id = azapi_resource.res-1.id
  type      = "Microsoft.ServiceBus/namespaces/topics@2025-05-01-preview"
}
resource "azapi_resource" "res-9" {
  body = {
    properties = {
      autoDeleteOnIdle                          = "P10675199DT2H48M5.4775807S"
      deadLetteringOnFilterEvaluationExceptions = true
      deadLetteringOnMessageExpiration          = true
      defaultMessageTimeToLive                  = "P7D"
      enableBatchedOperations                   = true
      isClientAffine                            = false
      lockDuration                              = "PT1M"
      maxDeliveryCount                          = 10
      requiresSession                           = false
      status                                    = "Active"
    }
  }
  name      = "audit"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.ServiceBus/namespaces/topics/subscriptions@2025-05-01-preview"
}
resource "azapi_resource" "res-10" {
  body = {
    properties = {
      autoDeleteOnIdle                          = "P10675199DT2H48M5.4775807S"
      deadLetteringOnFilterEvaluationExceptions = true
      deadLetteringOnMessageExpiration          = true
      defaultMessageTimeToLive                  = "P7D"
      enableBatchedOperations                   = true
      isClientAffine                            = false
      lockDuration                              = "PT1M"
      maxDeliveryCount                          = 10
      requiresSession                           = false
      status                                    = "Active"
    }
  }
  name      = "itsm"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.ServiceBus/namespaces/topics/subscriptions@2025-05-01-preview"
}
resource "azapi_resource" "res-11" {
  body = {
    properties = {
      autoDeleteOnIdle                          = "P10675199DT2H48M5.4775807S"
      deadLetteringOnFilterEvaluationExceptions = true
      deadLetteringOnMessageExpiration          = true
      defaultMessageTimeToLive                  = "P7D"
      enableBatchedOperations                   = true
      isClientAffine                            = false
      lockDuration                              = "PT1M"
      maxDeliveryCount                          = 10
      requiresSession                           = false
      status                                    = "Active"
    }
  }
  name      = "monitoring"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.ServiceBus/namespaces/topics/subscriptions@2025-05-01-preview"
}
resource "azapi_resource" "res-12" {
  body = {
    properties = {
      autoDeleteOnIdle                          = "P10675199DT2H48M5.4775807S"
      deadLetteringOnFilterEvaluationExceptions = true
      deadLetteringOnMessageExpiration          = true
      defaultMessageTimeToLive                  = "P7D"
      enableBatchedOperations                   = true
      isClientAffine                            = false
      lockDuration                              = "PT1M"
      maxDeliveryCount                          = 10
      requiresSession                           = true
      status                                    = "Active"
    }
  }
  name      = "orchestration"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.ServiceBus/namespaces/topics/subscriptions@2025-05-01-preview"
}
resource "azapi_resource" "res-13" {
  body = {
    properties = {
      autoDeleteOnIdle                          = "P10675199DT2H48M5.4775807S"
      deadLetteringOnFilterEvaluationExceptions = true
      deadLetteringOnMessageExpiration          = true
      defaultMessageTimeToLive                  = "P7D"
      enableBatchedOperations                   = true
      isClientAffine                            = false
      lockDuration                              = "PT1M"
      maxDeliveryCount                          = 10
      requiresSession                           = false
      status                                    = "Active"
    }
  }
  name      = "teams"
  parent_id = azapi_resource.res-8.id
  type      = "Microsoft.ServiceBus/namespaces/topics/subscriptions@2025-05-01-preview"
}
