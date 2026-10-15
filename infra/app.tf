locals {
  functions = {
    api       = { handler = "scale_mobili.app.handler", timeout = 15 }
    aggregate = { handler = "scale_mobili.workers.aggregate_handler", timeout = 30 }
    collector = { handler = "scale_mobili.workers.collector_handler", timeout = 30 }
  }
  runtime_environment = {
    SMT_MODE                    = "aws"
    SMT_REGION                  = var.region
    SMT_CORE_TABLE              = aws_dynamodb_table.prototype["core"].name
    SMT_EVENTS_TABLE            = aws_dynamodb_table.prototype["events"].name
    SMT_PHOTOS_BUCKET           = aws_s3_bucket.private["photos"].id
    SMT_SOURCES_BUCKET          = aws_s3_bucket.private["sources"].id
    SMT_PUBLIC_URL              = aws_apigatewayv2_api.backend.api_endpoint
    SMT_FRONTEND_URL            = var.frontend_url
    SMT_COGNITO_ISSUER          = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
    SMT_COGNITO_CLIENT_ID       = aws_cognito_user_pool_client.web.id
    SMT_COGNITO_DOMAIN          = "https://${aws_cognito_user_pool_domain.users.domain}.auth.${var.region}.amazoncognito.com"
    SMT_ADDITIONAL_CLIENT_IDS   = jsonencode(var.additional_client_ids)
    SMT_CURSOR_SECRET_PARAMETER = aws_ssm_parameter.cursor.name
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.functions
  name              = "/aws/lambda/${var.prefix}-${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "lambda" {
  for_each             = local.functions
  name                 = "${var.prefix}-${each.key}"
  permissions_boundary = var.runtime_permissions_boundary_arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.functions
  name     = "${var.prefix}-${each.key}"
  role     = aws_iam_role.lambda[each.key].id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([
    {
      Sid      = "DedicatedDynamoDB", Effect = "Allow",
      Action   = ["dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:ConditionCheckItem"],
      Resource = concat([for table in aws_dynamodb_table.prototype : table.arn], [for table in aws_dynamodb_table.prototype : "${table.arn}/index/*"])
    },
    { Sid = "CursorParameter", Effect = "Allow", Action = ["ssm:GetParameter"], Resource = aws_ssm_parameter.cursor.arn },
    { Sid      = "CursorDecryption", Effect = "Allow", Action = ["kms:Decrypt"],
      Resource = "arn:${data.aws_partition.current.partition}:kms:${var.region}:${data.aws_caller_identity.current.account_id}:key/*",
    Condition = { StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com", "kms:EncryptionContext:PARAMETER_ARN" = aws_ssm_parameter.cursor.arn } } },
    { Sid = "DedicatedLogs", Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lambda[each.key].arn}:*" }
    ], each.key == "api" ? [{
      Sid      = "PrivatePhotos", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      Resource = "${aws_s3_bucket.private["photos"].arn}/*"
      }] : [], contains(["api", "collector"], each.key) ? [{
      Sid      = "PrivateOriginals", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"],
      Resource = "${aws_s3_bucket.private["sources"].arn}/originals/*"
  }] : []) })
}

resource "aws_lambda_function" "backend" {
  for_each                       = local.functions
  function_name                  = "${var.prefix}-${each.key}"
  role                           = aws_iam_role.lambda[each.key].arn
  runtime                        = "python3.12"
  architectures                  = ["x86_64"]
  handler                        = each.value.handler
  filename                       = var.lambda_zip_path
  source_code_hash               = fileexists(var.lambda_zip_path) ? filebase64sha256(var.lambda_zip_path) : null
  memory_size                    = 512
  timeout                        = each.value.timeout
  reserved_concurrent_executions = var.reserved_concurrency
  logging_config {
    log_format            = "JSON"
    application_log_level = "WARN"
    system_log_level      = "WARN"
    log_group             = aws_cloudwatch_log_group.lambda[each.key].name
  }
  environment {
    variables = merge(local.runtime_environment, each.key == "collector" ? { SMT_WRITE_LIMIT_PER_MINUTE = "100" } : {})
  }
  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.lambda]
  lifecycle {
    precondition {
      condition     = fileexists(var.lambda_zip_path)
      error_message = "Creare prima il pacchetto con scripts/build_lambda.py."
    }
  }
}

resource "aws_apigatewayv2_api" "backend" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins  = [var.frontend_url]
    allow_methods  = ["GET", "POST", "PUT", "OPTIONS"]
    allow_headers  = ["Authorization", "Content-Type", "Idempotency-Key", "Mcp-Protocol-Version"]
    expose_headers = ["WWW-Authenticate"]
    max_age        = 300
  }
}

resource "aws_apigatewayv2_integration" "backend" {
  api_id                 = aws_apigatewayv2_api.backend.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.backend["api"].invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "backend" {
  api_id    = aws_apigatewayv2_api.backend.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.backend.id}"
  # Le letture pubbliche e il protocollo MCP condividono il trasporto.
  # Ogni operazione riservata verifica JWT, scope e ruolo nel backend Python.
}

resource "aws_apigatewayv2_stage" "backend" {
  api_id      = aws_apigatewayv2_api.backend.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = var.api_rate_limit
    throttling_burst_limit = var.api_burst_limit
  }
}

resource "aws_lambda_permission" "gateway" {
  statement_id  = "DedicatedHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend["api"].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.backend.execution_arn}/*/*"
}
