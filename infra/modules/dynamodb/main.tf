variable "prefix" {
  type = string
}

variable "enable_deletion_protection" {
  type = bool
}

# The application contracts use these four tables. The table partition key is
# "id"; no secondary indexes are used or required by the inspected access paths.
resource "aws_dynamodb_table" "service" {
  for_each                    = toset(["stations", "wallets", "dispatch", "sagas", "flags"])
  name                        = "${var.prefix}-${each.key}"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "id"
  deletion_protection_enabled = var.enable_deletion_protection

  attribute {
    name = "id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    DataContract = each.key
  }
}

variable "initial_feature_flags" {
  description = "Initial per-environment flag values. Seeded once; later runtime changes in DynamoDB are not reverted by Terraform."
  type        = map(bool)
}

# One item per official flag in this environment's own flags table. Operators
# toggle them at runtime (scripts/set_feature_flag.py); ignore_changes keeps
# terraform apply from overwriting a live demo/operational change.
resource "aws_dynamodb_table_item" "feature_flag" {
  for_each   = var.initial_feature_flags
  table_name = aws_dynamodb_table.service["flags"].name
  hash_key   = "id"
  item = jsonencode({
    id      = { S = each.key }
    enabled = { BOOL = each.value }
  })
  lifecycle { ignore_changes = [item] }
}

output "table_names" {
  value = { for name, table in aws_dynamodb_table.service : name => table.name }
}

output "table_arns" {
  value = { for name, table in aws_dynamodb_table.service : name => table.arn }
}
