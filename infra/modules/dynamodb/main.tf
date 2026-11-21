variable "prefix" { type = string }
resource "aws_dynamodb_table" "service" {
  for_each     = toset(["stations", "wallets", "dispatch", "sagas", "feature-flags", "reservations", "billing"])
  name         = "${var.prefix}-${each.key}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
}
