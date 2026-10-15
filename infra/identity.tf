resource "aws_cognito_user_pool" "users" {
  name                     = "${var.prefix}-users"
  user_pool_tier           = "ESSENTIALS"
  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]
  deletion_protection      = "ACTIVE"
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }
  admin_create_user_config { allow_admin_create_user_only = true }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_domain" "users" {
  domain                = "${var.prefix}-${data.aws_caller_identity.current.account_id}"
  user_pool_id          = aws_cognito_user_pool.users.id
  managed_login_version = 2
}

resource "aws_cognito_resource_server" "platform" {
  identifier   = "scale-mobili"
  name         = "Scale Mobili Torino"
  user_pool_id = aws_cognito_user_pool.users.id
  scope {
    scope_name        = "reports:write"
    scope_description = "Segnalazioni, proposte e foto con identità verificata"
  }
  scope {
    scope_name        = "stats:read"
    scope_description = "Confronto delle fonti e statistiche riservate"
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${var.prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "scale-mobili/reports:write", "scale-mobili/stats:read"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = distinct(concat(["${var.frontend_url}/callback"], var.callback_urls))
  logout_urls                          = [var.frontend_url]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  depends_on                    = [aws_cognito_resource_server.platform]
}

resource "aws_cognito_user_group" "moderators" {
  name         = "moderators"
  user_pool_id = aws_cognito_user_pool.users.id
  description  = "Revisione server di impianti, foto e interpretazioni delle fonti"
}

# Il binding OAuth resource -> aud richiesto da MCP usa managed login.
resource "aws_cognito_managed_login_branding" "web" {
  client_id                   = aws_cognito_user_pool_client.web.id
  user_pool_id                = aws_cognito_user_pool.users.id
  use_cognito_provided_values = true
}

resource "aws_ssm_parameter" "cursor" {
  name             = "/${var.prefix}/cursor-secret"
  type             = "SecureString"
  value_wo         = var.cursor_secret
  value_wo_version = var.cursor_secret_version
}
