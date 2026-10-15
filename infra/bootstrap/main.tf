terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.68" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "scale-mobili-torino", Environment = "bootstrap" }
  }
}

variable "region" {
  type    = string
  default = "eu-south-1"
}
variable "prefix" {
  type    = string
  default = "scale-mobili-prototype"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.prefix))
    error_message = "Prefisso dedicato di 3–40 caratteri."
  }
}
variable "github_repository" {
  type        = string
  description = "owner/repo esatto, senza wildcard."
  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", var.github_repository))
    error_message = "Usare owner/repo senza wildcard."
  }
}
variable "github_environment" {
  type    = string
  default = "aws-prototype"
}
variable "existing_oidc_provider_arn" {
  type        = string
  default     = ""
  description = "Riusare solo il provider GitHub verificato; ruoli e stato restano dedicati."
}
variable "budget_reviewed" {
  type    = bool
  default = false
  validation {
    condition     = var.budget_reviewed
    error_message = "Anche il bootstrap richiede la verifica economica."
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  partition     = data.aws_partition.current.partition
  account       = data.aws_caller_identity.current.account_id
  oidc          = var.existing_oidc_provider_arn != "" ? var.existing_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
  table_arns    = ["arn:${local.partition}:dynamodb:${var.region}:${local.account}:table/${var.prefix}-*"]
  runtime_roles = [for suffix in ["api", "aggregate", "collector", "scheduler"] : "arn:${local.partition}:iam::${local.account}:role/${var.prefix}-${suffix}"]
  trust = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = local.oidc }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:environment:${var.github_environment}"
    } }
  }] })
}

resource "aws_s3_bucket" "state" {
  bucket        = "${var.prefix}-state-${local.account}"
  force_destroy = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-deployment-plans"
    status = "Enabled"
    filter { prefix = "scale-mobili/prototype/plans/" }
    expiration { days = 7 }
    noncurrent_version_expiration { noncurrent_days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
  # Lo stato corrente non scade. Restano 30 giorni delle versioni precedenti.
  rule {
    id     = "retain-previous-state-versions"
    status = "Enabled"
    filter { prefix = "scale-mobili/prototype/terraform.tfstate" }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
  depends_on = [aws_s3_bucket_versioning.state]
}

resource "aws_iam_policy" "runtime_boundary" {
  name = "${var.prefix}-runtime-boundary"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:TransactWriteItems"], Resource = concat(local.table_arns, [for arn in local.table_arns : "${arn}/index/*"]) },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = ["arn:${local.partition}:s3:::${var.prefix}-photos-${local.account}/*", "arn:${local.partition}:s3:::${var.prefix}-sources-${local.account}/originals/*"] },
    { Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:${local.partition}:ssm:${var.region}:${local.account}:parameter/${var.prefix}/cursor-secret" },
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = "arn:${local.partition}:kms:${var.region}:${local.account}:key/*", Condition = { StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com", "kms:EncryptionContext:PARAMETER_ARN" = "arn:${local.partition}:ssm:${var.region}:${local.account}:parameter/${var.prefix}/cursor-secret" } } },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:${local.partition}:logs:${var.region}:${local.account}:log-group:/aws/lambda/${var.prefix}-*:*" },
    { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = "arn:${local.partition}:lambda:${var.region}:${local.account}:function:${var.prefix}-*" }
  ] })
}

resource "aws_iam_role" "github" {
  for_each             = toset(["plan", "deploy"])
  name                 = "${var.prefix}-${each.key}"
  assume_role_policy   = local.trust
  max_session_duration = 3600
}

locals {
  state_statements = [
    { Effect = "Allow", Action = ["s3:ListBucket", "s3:GetBucketLocation"], Resource = aws_s3_bucket.state.arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.state.arn}/scale-mobili/prototype/*" },
    { Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "${aws_s3_bucket.state.arn}/scale-mobili/prototype/*.tflock" }
  ]
  read_statements = [
    { Effect = "Allow", Action = ["sts:GetCallerIdentity"], Resource = "*" },
    { Effect = "Allow", Action = ["dynamodb:DescribeTable", "dynamodb:DescribeContinuousBackups", "dynamodb:DescribeTimeToLive", "dynamodb:ListTagsOfResource"], Resource = local.table_arns },
    { Effect = "Allow", Action = ["lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:GetPolicy", "lambda:ListVersionsByFunction", "lambda:GetFunctionConcurrency", "lambda:ListTags"], Resource = "arn:${local.partition}:lambda:${var.region}:${local.account}:function:${var.prefix}-*" },
    { Effect = "Allow", Action = ["s3:GetBucket*", "s3:ListBucket"], Resource = "arn:${local.partition}:s3:::${var.prefix}-*" },
    { Effect = "Allow", Action = ["iam:GetRole", "iam:GetRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies"], Resource = local.runtime_roles },
    { Effect = "Allow", Action = ["ssm:GetParameter", "ssm:ListTagsForResource"], Resource = "arn:${local.partition}:ssm:${var.region}:${local.account}:parameter/${var.prefix}/*" },
    { Effect = "Allow", Action = ["cognito-idp:DescribeUserPool", "cognito-idp:DescribeUserPoolClient", "cognito-idp:DescribeUserPoolDomain", "cognito-idp:DescribeResourceServer", "cognito-idp:GetGroup", "cognito-idp:ListTagsForResource"], Resource = "arn:${local.partition}:cognito-idp:${var.region}:${local.account}:userpool/*" },
    { Effect = "Allow", Action = ["apigateway:GET"], Resource = "arn:${local.partition}:apigateway:${var.region}::*" },
    { Effect = "Allow", Action = ["logs:DescribeLogGroups", "logs:ListTagsForResource"], Resource = "*" },
    { Effect = "Allow", Action = ["scheduler:GetSchedule", "scheduler:ListTagsForResource"], Resource = "arn:${local.partition}:scheduler:${var.region}:${local.account}:schedule/default/${var.prefix}-*" }
  ]
  deploy_statements = [
    { Effect = "Allow", Action = ["dynamodb:CreateTable", "dynamodb:UpdateTable", "dynamodb:DeleteTable", "dynamodb:UpdateTimeToLive", "dynamodb:TagResource", "dynamodb:UntagResource"], Resource = local.table_arns },
    { Effect = "Allow", Action = ["lambda:CreateFunction", "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration", "lambda:DeleteFunction", "lambda:AddPermission", "lambda:RemovePermission", "lambda:PutFunctionConcurrency", "lambda:DeleteFunctionConcurrency", "lambda:TagResource", "lambda:UntagResource"], Resource = "arn:${local.partition}:lambda:${var.region}:${local.account}:function:${var.prefix}-*" },
    { Effect = "Allow", Action = ["s3:*"], Resource = ["arn:${local.partition}:s3:::${var.prefix}-photos-${local.account}", "arn:${local.partition}:s3:::${var.prefix}-photos-${local.account}/*", "arn:${local.partition}:s3:::${var.prefix}-sources-${local.account}", "arn:${local.partition}:s3:::${var.prefix}-sources-${local.account}/*"] },
    { Effect = "Allow", Action = ["iam:CreateRole"], Resource = local.runtime_roles, Condition = { StringEquals = { "iam:PermissionsBoundary" = aws_iam_policy.runtime_boundary.arn } } },
    { Effect = "Allow", Action = ["iam:DeleteRole", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole"], Resource = local.runtime_roles },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = local.runtime_roles, Condition = { StringEquals = { "iam:PassedToService" = ["lambda.amazonaws.com", "scheduler.amazonaws.com"] } } },
    { Effect = "Allow", Action = ["ssm:PutParameter", "ssm:DeleteParameter", "ssm:AddTagsToResource", "ssm:RemoveTagsFromResource"], Resource = "arn:${local.partition}:ssm:${var.region}:${local.account}:parameter/${var.prefix}/*" },
    { Effect = "Allow", Action = ["cognito-idp:CreateUserPool", "cognito-idp:UpdateUserPool", "cognito-idp:DeleteUserPool", "cognito-idp:CreateUserPoolClient", "cognito-idp:UpdateUserPoolClient", "cognito-idp:DeleteUserPoolClient", "cognito-idp:CreateUserPoolDomain", "cognito-idp:DeleteUserPoolDomain", "cognito-idp:CreateResourceServer", "cognito-idp:UpdateResourceServer", "cognito-idp:DeleteResourceServer", "cognito-idp:CreateGroup", "cognito-idp:UpdateGroup", "cognito-idp:DeleteGroup", "cognito-idp:TagResource", "cognito-idp:UntagResource"], Resource = "arn:${local.partition}:cognito-idp:${var.region}:${local.account}:userpool/*" },
    { Effect = "Allow", Action = ["apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], Resource = "arn:${local.partition}:apigateway:${var.region}::*" },
    { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy", "logs:TagResource", "logs:UntagResource"], Resource = "arn:${local.partition}:logs:${var.region}:${local.account}:log-group:/aws/lambda/${var.prefix}-*:*" },
    { Effect = "Allow", Action = ["scheduler:CreateSchedule", "scheduler:UpdateSchedule", "scheduler:DeleteSchedule", "scheduler:TagResource", "scheduler:UntagResource"], Resource = "arn:${local.partition}:scheduler:${var.region}:${local.account}:schedule/default/${var.prefix}-*" }
  ]
}

resource "aws_iam_role_policy" "github" {
  for_each = toset(["plan", "deploy"])
  name     = "${var.prefix}-${each.key}"
  role     = aws_iam_role.github[each.key].id
  policy   = jsonencode({ Version = "2012-10-17", Statement = concat(local.state_statements, local.read_statements, jsondecode(each.key == "deploy" ? jsonencode(local.deploy_statements) : "[]")) })
}

output "state_bucket" { value = aws_s3_bucket.state.id }
output "plan_role_arn" { value = aws_iam_role.github["plan"].arn }
output "deploy_role_arn" { value = aws_iam_role.github["deploy"].arn }
output "runtime_permissions_boundary_arn" { value = aws_iam_policy.runtime_boundary.arn }
