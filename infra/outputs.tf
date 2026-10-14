output "proposed_capacity" {
  value = {
    total_rcu = 7
    total_wcu = 7
    tables    = 2
    indexes   = 3
  }
  description = "Allocazione della prova, da confrontare con il consumo già presente."
}

output "api_url" { value = aws_apigatewayv2_api.backend.api_endpoint }
output "mcp_url" { value = "${aws_apigatewayv2_api.backend.api_endpoint}/mcp" }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_domain" { value = "https://${aws_cognito_user_pool_domain.users.domain}.auth.${var.region}.amazoncognito.com" }
output "core_table" { value = aws_dynamodb_table.prototype["core"].name }
output "events_table" { value = aws_dynamodb_table.prototype["events"].name }
output "photos_bucket" { value = aws_s3_bucket.private["photos"].id }
output "sources_bucket" { value = aws_s3_bucket.private["sources"].id }
output "cursor_secret_parameter" { value = aws_ssm_parameter.cursor.name }
output "aggregate_function" { value = aws_lambda_function.backend["aggregate"].function_name }
output "collector_function" { value = aws_lambda_function.backend["collector"].function_name }
