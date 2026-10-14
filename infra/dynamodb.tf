locals {
  tables = {
    core = { indexes = {
      by_station   = { pk = "station_pk", sk = "station_sk" }
      review_queue = { pk = "review_pk", sk = "review_sk" }
    } }
    events = { indexes = {
      by_actor = { pk = "actor_pk", sk = "actor_sk" }
    } }
  }
}

resource "aws_dynamodb_table" "prototype" {
  for_each       = local.tables
  name           = "${var.prefix}-${each.key}"
  billing_mode   = "PROVISIONED"
  table_class    = "STANDARD"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = 2
  write_capacity = 2

  dynamic "attribute" {
    for_each = toset(concat(["PK", "SK"], flatten([
      for index in values(each.value.indexes) : [index.pk, index.sk]
    ])))
    content {
      name = attribute.value
      type = "S"
    }
  }

  dynamic "global_secondary_index" {
    for_each = each.value.indexes
    content {
      name            = global_secondary_index.key
      hash_key        = global_secondary_index.value.pk
      range_key       = global_secondary_index.value.sk
      projection_type = "KEYS_ONLY"
      read_capacity   = 1
      write_capacity  = 1
    }
  }

  dynamic "ttl" {
    for_each = each.key == "core" ? [1] : []
    content {
      attribute_name = "expires_at"
      enabled        = true
    }
  }

  server_side_encryption { enabled = true }
}
