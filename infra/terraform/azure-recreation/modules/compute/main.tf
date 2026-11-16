resource "azapi_resource" "res-1" {
  body = {
    properties = {
      creationData = {
        createOption = "Empty"
      }
      dataAccessAuthMode = "None"
      diskIOPSReadWrite  = 500
      diskMBpsReadWrite  = 60
      diskSizeGB         = 32
      encryption = {
        type = "EncryptionAtRestWithPlatformKey"
      }
      networkAccessPolicy = "AllowAll"
      publicNetworkAccess = "Enabled"
    }
    sku = {
      name = "Standard_LRS"
    }
    zones = ["1"]
  }
  location  = "eastus"
  name      = "disk_demo_pco"
  parent_id = var.ref_foundation_res_7_id
  type      = "Microsoft.Compute/disks@2025-01-02"
}
resource "azapi_resource" "res-2" {
  body = {
    properties = {
      creationData = {
        createOption = "FromImage"
        imageReference = {
          id = "/Subscriptions/${var.subscription_id}/Providers/Microsoft.Compute/Locations/eastus2/Publishers/Canonical/ArtifactTypes/VMImage/Offers/0001-com-ubuntu-server-jammy/Skus/22_04-lts-gen2/Versions/22.04.202608060"
        }
      }
      diskIOPSReadWrite = 500
      diskMBpsReadWrite = 100
      diskSizeGB        = 30
      encryption = {
        type = "EncryptionAtRestWithPlatformKey"
      }
      hyperVGeneration    = "V2"
      networkAccessPolicy = "AllowAll"
      osType              = "Linux"
      publicNetworkAccess = "Enabled"
      supportedCapabilities = {
        acceleratedNetwork  = true
        architecture        = "x64"
        diskControllerTypes = "SCSI, NVMe"
      }
      supportsHibernation = true
    }
    sku = {
      name = "StandardSSD_LRS"
    }
  }
  location  = "eastus2"
  name      = "osdisk-vm-icenter-sbx-demo-01"
  parent_id = var.ref_foundation_res_7_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Compute/disks@2025-01-02"
}
resource "azapi_resource" "res-3" {
  body = {
    properties = {
      hardwareProfile = {
        vmSize = "Standard_D2als_v7"
      }
      networkProfile = {
        networkInterfaces = [{
          id = "${var.ref_network_res_10_id}"
          properties = {
            primary = true
          }
        }]
      }
      osProfile = {
        adminUsername            = "azureuser"
        allowExtensionOperations = true
        computerName             = "vm-icenter-sbx-demo-01"
        linuxConfiguration = {
          disablePasswordAuthentication = true
          patchSettings = {
            assessmentMode = "ImageDefault"
            patchMode      = "ImageDefault"
          }
          provisionVMAgent = true
          ssh = {
            publicKeys = [{
              keyData = var.vm_ssh_public_key
              path    = "/home/azureuser/.ssh/authorized_keys"
            }]
          }
        }
        requireGuestProvisionSignal = true
        secrets                     = []
      }
      storageProfile = {
        dataDisks          = []
        diskControllerType = "NVMe"
        imageReference = {
          offer     = "0001-com-ubuntu-server-jammy"
          publisher = "Canonical"
          sku       = "22_04-lts-gen2"
          version   = "latest"
        }
        osDisk = {
          caching      = "ReadWrite"
          createOption = "FromImage"
          deleteOption = "Detach"
          managedDisk = {
            id = azapi_resource.res-2.id
          }
          name   = "osdisk-vm-icenter-sbx-demo-01"
          osType = "Linux"
        }
      }
    }
  }
  location  = "eastus2"
  name      = "vm-icenter-sbx-demo-01"
  parent_id = var.ref_foundation_res_7_id
  tags = {
    costCenter  = "inaki-poc"
    environment = "sandbox"
    expiration  = "2026-09-05"
    managedBy   = "powershell-azure-cli"
    owner       = "icenter-microsoft"
    project     = "ai-support-platform"
  }
  type = "Microsoft.Compute/virtualMachines@2025-04-01"
}
