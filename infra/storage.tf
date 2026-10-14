data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  buckets = {
    photos  = "${var.prefix}-photos-${data.aws_caller_identity.current.account_id}"
    sources = "${var.prefix}-sources-${data.aws_caller_identity.current.account_id}"
  }
}

resource "aws_s3_bucket" "private" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "private" {
  for_each                = local.buckets
  bucket                  = aws_s3_bucket.private[each.key].id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "private" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.private[each.key].id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.private[each.key].id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_policy" "tls" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.private[each.key].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [aws_s3_bucket.private[each.key].arn, "${aws_s3_bucket.private[each.key].arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}

resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.private["photos"].id
  cors_rule {
    allowed_origins = [var.frontend_url]
    allowed_methods = ["POST"]
    allowed_headers = ["*"]
    max_age_seconds = 300
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.private["photos"].id
  rule {
    id     = "expire-unprocessed-uploads"
    status = "Enabled"
    filter { prefix = "uploads/" }
    expiration { days = 1 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}
