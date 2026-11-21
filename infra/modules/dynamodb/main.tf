variable "prefix" {
  type = string
}

variable "enable_deletion_protection" {
  type = bool
}

# The application contracts use these four tables. The table partition key is
# "id"; no secondary indexes are used or required by the inspected access paths.
resource "aws_dynamodb_table" "service" {
  for_each                    = toset(["stations", "wallets", "dispatch", "sagas"])
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

output "table_names" {
  value = { for name, table in aws_dynamodb_table.service : name => table.name }
}

output "table_arns" {
  value = { for name, table in aws_dynamodb_table.service : name => table.arn }
}
