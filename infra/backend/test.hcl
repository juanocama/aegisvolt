bucket       = "aegisvolt-tfstate-065656773005-us-east-1"
# One key for all environments: `terraform workspace select <env>` stores
# state at env:/<env>/aegisvolt/terraform.tfstate in the versioned bucket.
key          = "aegisvolt/terraform.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true
