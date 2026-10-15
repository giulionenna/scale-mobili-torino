mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "000000000000" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::000000000000:oidc-provider/token.actions.githubusercontent.com" }
  }
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::000000000000:policy/test-runtime-boundary" }
  }
}

variables {
  github_repository     = "example/project"
  github_subject_prefix = "repo:example/project"
  budget_reviewed       = true
}

run "isolated_bootstrap" {
  command = apply
  assert {
    condition     = jsondecode(aws_iam_role.github["deploy"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example/project:environment:aws-prototype"
    error_message = "La trust OIDC deve essere vincolata al repository e all'environment esatti."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "Lo stato deve restare privato e versionato."
  }
  assert {
    condition     = !contains(jsondecode(aws_iam_policy.runtime_boundary.policy).Statement[0].Action, "dynamodb:Scan") && contains(jsondecode(aws_iam_policy.runtime_boundary.policy).Statement[0].Action, "dynamodb:ConditionCheckItem")
    error_message = "Il boundary deve permettere le condizioni delle transazioni senza Scan."
  }
  assert {
    condition = alltrue([for statement in jsondecode(aws_iam_role_policy.github["deploy"].policy).Statement : (
      statement.Resource == "*" && statement.Condition.StringEquals["aws:RequestTag/Project"] == "scale-mobili-torino" && statement.Condition.StringEquals["aws:RequestTag/Environment"] == "prototype" && statement.Condition.StringEquals["aws:RequestedRegion"] == "eu-south-1"
    ) if contains(statement.Action, "cognito-idp:CreateUserPool")])
    error_message = "CreateUserPool non supporta ARN di risorsa: vincolare la creazione ai tag e alla regione del progetto."
  }
  assert {
    condition = alltrue([for role in ["plan", "deploy"] : alltrue([for action in ["s3:GetLifecycleConfiguration", "s3:GetReplicationConfiguration", "s3:GetEncryptionConfiguration", "s3:GetAccelerateConfiguration"] : anytrue([for statement in jsondecode(aws_iam_role_policy.github[role].policy).Statement :
      contains(statement.Action, action)
    ])])])
    error_message = "Le letture di lifecycle, replica, cifratura e accelerazione S3 non rientrano in GetBucket*."
  }
  assert {
    condition = alltrue([for role in ["plan", "deploy"] : anytrue([for statement in jsondecode(aws_iam_role_policy.github[role].policy).Statement : try(
      contains(statement.Action, "ssm:DescribeParameters") && statement.Resource == "*" && statement.Condition.StringEquals["aws:RequestedRegion"] == "eu-south-1", false
    )])])
    error_message = "Il refresh SSM richiede DescribeParameters limitato alla regione, per entrambi i ruoli OIDC."
  }
  assert {
    condition     = anytrue([for statement in jsondecode(aws_iam_role_policy.github["deploy"].policy).Statement : contains(statement.Action, "apigateway:TagResource")]) && !anytrue([for statement in jsondecode(aws_iam_role_policy.github["plan"].policy).Statement : contains(statement.Action, "apigateway:TagResource")])
    error_message = "Solo il deploy deve poter applicare i tag durante CreateStage."
  }
  assert {
    condition = alltrue([for role in ["plan", "deploy"] : alltrue([for action in ["cognito-idp:DescribeManagedLoginBranding", "cognito-idp:DescribeManagedLoginBrandingByClient", "cognito-idp:ListUserPoolClients"] : anytrue([for statement in jsondecode(aws_iam_role_policy.github[role].policy).Statement :
      contains(statement.Action, action)
    ])])])
    error_message = "Il refresh dello stile gestito enumera i client e legge il branding per client nel pool."
  }
  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.state.rule) == 2 && alltrue([for rule in aws_s3_bucket_lifecycle_configuration.state.rule : rule.filter[0].prefix == "scale-mobili/prototype/terraform.tfstate" ? length(rule.expiration) == 0 : rule.expiration[0].days == 7])
    error_message = "I vecchi bundle devono scadere senza eliminare lo stato Terraform corrente."
  }
}

run "immutable_repository_subject" {
  command = plan
  variables { github_subject_prefix = "repo:example@123/project@456" }
  assert {
    condition     = jsondecode(aws_iam_role.github["plan"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example@123/project@456:environment:aws-prototype"
    error_message = "La trust deve conservare gli ID immutabili osservati da GitHub."
  }
}

run "reject_other_repository_subject" {
  command = plan
  variables { github_subject_prefix = "repo:other@123/project@456" }
  expect_failures = [var.github_subject_prefix]
}

run "bootstrap_budget_guard" {
  command = plan
  variables { budget_reviewed = false }
  expect_failures = [var.budget_reviewed]
}
