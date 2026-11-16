terraform {
  required_version = "= 1.9.6"
  required_providers {
    azapi = {
      source  = "azure/azapi"
      version = "2.9.0"
    }
  }
}
