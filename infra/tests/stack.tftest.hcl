mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::000000000000:role/mock-runtime-role" }
  }
  mock_resource "aws_cognito_user_pool" {
    defaults = { id = "eu-south-1_Ab123456" }
  }
  mock_resource "aws_lambda_function" {
    defaults = {
      arn        = "arn:aws:lambda:eu-south-1:000000000000:function:mock-function"
      invoke_arn = "arn:aws:apigateway:eu-south-1:lambda:path/2015-03-31/functions/arn:aws:lambda:eu-south-1:000000000000:function:mock-function/invocations"
    }
  }
  mock_resource "aws_apigatewayv2_api" {
    defaults = {
      api_endpoint  = "https://test-api.execute-api.eu-south-1.amazonaws.com"
      execution_arn = "arn:aws:execute-api:eu-south-1:000000000000:test-api"
    }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "000000000000" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
}

variables {
  frontend_url                     = "https://frontend.example"
  cursor_secret                    = "test-only-random-cursor-secret-never-for-production"
  budget_reviewed                  = true
  runtime_permissions_boundary_arn = "arn:aws:iam::000000000000:policy/test-runtime-boundary"
}

run "protected_backend" {
  command = apply
  assert {
    condition     = length(aws_lambda_function.backend) == 3
    error_message = "Servono API, aggregatore e collector."
  }
  assert {
    condition     = length(aws_scheduler_schedule.worker) == 0
    error_message = "Nessuna acquisizione periodica deve partire di default."
  }
  assert {
    condition     = alltrue([for bucket in aws_s3_bucket_public_access_block.private : bucket.block_public_policy && bucket.block_public_acls && bucket.ignore_public_acls && bucket.restrict_public_buckets])
    error_message = "Foto e originali devono restare privati."
  }
  assert {
    condition     = alltrue([for function in aws_lambda_function.backend : function.environment[0].variables.SMT_MODE == "aws"])
    error_message = "Identità demo vietate su Lambda."
  }
  assert {
    condition     = !contains(jsondecode(aws_iam_role_policy.lambda["api"].policy).Statement[0].Action, "dynamodb:Scan")
    error_message = "Il runtime API non deve poter eseguire Scan."
  }
  assert {
    condition     = !aws_cognito_user_pool_client.web.generate_secret && aws_cognito_user_pool_client.web.allowed_oauth_flows == toset(["code"])
    error_message = "Client pubblico con authorization code e PKCE."
  }
  assert {
    condition     = output.proposed_capacity.total_rcu == 7 && output.proposed_capacity.total_wcu == 7
    error_message = "Il dimensionamento deve includere tutti i GSI."
  }
}

run "budget_blocks_unreviewed_plan" {
  command = plan
  variables { budget_reviewed = false }
  expect_failures = [var.budget_reviewed]
}
