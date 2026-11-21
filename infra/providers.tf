provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "AegisVolt"
      Environment = terraform.workspace
      ManagedBy   = "Terraform"
    }
  }
}
