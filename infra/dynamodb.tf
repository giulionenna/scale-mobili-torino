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
  billing_mode   = var.dynamodb_billing_mode
  table_class    = "STANDARD"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = var.dynamodb_billing_mode == "PROVISIONED" ? 2 : null
  write_capacity = var.dynamodb_billing_mode == "PROVISIONED" ? 2 : null

  dynamic "on_demand_throughput" {
    for_each = var.dynamodb_billing_mode == "PAY_PER_REQUEST" ? [1] : []
    content {
      max_read_request_units  = var.dynamodb_max_read_units
      max_write_request_units = var.dynamodb_max_write_units
    }
  }

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
      name = global_secondary_index.key
      key_schema {
        attribute_name = global_secondary_index.value.pk
        key_type       = "HASH"
      }
      key_schema {
        attribute_name = global_secondary_index.value.sk
        key_type       = "RANGE"
      }
      projection_type = "KEYS_ONLY"
      read_capacity   = var.dynamodb_billing_mode == "PROVISIONED" ? 1 : null
      write_capacity  = var.dynamodb_billing_mode == "PROVISIONED" ? 1 : null
      dynamic "on_demand_throughput" {
        for_each = var.dynamodb_billing_mode == "PAY_PER_REQUEST" ? [1] : []
        content {
          max_read_request_units  = var.dynamodb_max_read_units
          max_write_request_units = var.dynamodb_max_write_units
        }
      }
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
