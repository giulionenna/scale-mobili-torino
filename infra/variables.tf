variable "region" {
  type    = string
  default = "eu-south-1"
}

variable "prefix" {
  type    = string
  default = "scale-mobili-prototype"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.prefix))
    error_message = "Usare un prefisso dedicato di 3–40 caratteri minuscoli."
  }
}

variable "budget_reviewed" {
  type        = bool
  default     = false
  description = "Impostare true solo dopo la verifica documentata di tutte le voci AWS."
  validation {
    condition     = var.budget_reviewed
    error_message = "La prova AWS richiede prima la verifica di tariffe, benefici residui e budget concordato."
  }
}

variable "frontend_url" {
  type        = string
  description = "Origine HTTPS del frontend; nessun path o slash finale."
  validation {
    condition     = can(regex("^https://[^/]+$", var.frontend_url))
    error_message = "Indicare un'origine HTTPS valida."
  }
}

variable "callback_urls" {
  type        = list(string)
  default     = []
  description = "Callback aggiuntive esplicitamente verificate, ad esempio per il client MCP."
  validation {
    condition     = alltrue([for url in var.callback_urls : can(regex("^https://", url))])
    error_message = "Le callback aggiuntive devono usare HTTPS."
  }
}

variable "lambda_zip_path" {
  type    = string
  default = "../dist/backend-lambda.zip"
}

variable "cursor_secret" {
  type        = string
  sensitive   = true
  ephemeral   = true
  description = "Segreto cursori di almeno 32 caratteri, scritto solo in SSM."
  validation {
    condition     = length(var.cursor_secret) >= 32
    error_message = "Servono almeno 32 caratteri casuali."
  }
}

variable "cursor_secret_version" {
  type        = number
  default     = 1
  description = "Incrementare esplicitamente per una rotazione del segreto."
}

variable "enable_schedules" {
  type        = bool
  default     = false
  description = "Disattivati inizialmente: abilitare dopo la verifica di costi e fonte."
}

variable "additional_client_ids" {
  type        = list(string)
  default     = []
  description = "Client Cognito aggiuntivi verificati; nessuna registrazione dinamica implicita."
}

variable "runtime_permissions_boundary_arn" {
  type        = string
  description = "Boundary dei ruoli Lambda/Scheduler, creato dal bootstrap dedicato."
  validation {
    condition     = can(regex("^arn:[^:]+:iam::[0-9]{12}:policy/", var.runtime_permissions_boundary_arn))
    error_message = "Indicare l'ARN del permissions boundary dedicato."
  }
}

variable "reserved_concurrency" {
  type    = number
  default = 1
  validation {
    condition     = var.reserved_concurrency >= 1 && var.reserved_concurrency <= 5
    error_message = "Il prototipo consente da 1 a 5 invocazioni concorrenti."
  }
}

variable "dynamodb_billing_mode" {
  type        = string
  default     = "PAY_PER_REQUEST"
  description = "A consumo per la prova; PROVISIONED solo dopo verifica del Free Tier residuo."
  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.dynamodb_billing_mode)
    error_message = "Modalità DynamoDB non valida."
  }
}

variable "dynamodb_max_read_units" {
  type    = number
  default = 100
  validation {
    condition     = var.dynamodb_max_read_units >= 1 && var.dynamodb_max_read_units <= 100 && floor(var.dynamodb_max_read_units) == var.dynamodb_max_read_units
    error_message = "Limite intero di 1–100 unità di lettura al secondo per tabella/indice."
  }
}

variable "dynamodb_max_write_units" {
  type    = number
  default = 20
  validation {
    condition     = var.dynamodb_max_write_units >= 1 && var.dynamodb_max_write_units <= 20 && floor(var.dynamodb_max_write_units) == var.dynamodb_max_write_units
    error_message = "Limite intero di 1–20 unità di scrittura al secondo per tabella/indice."
  }
}

variable "api_rate_limit" {
  type    = number
  default = 2
  validation {
    condition     = var.api_rate_limit >= 1 && var.api_rate_limit <= 10
    error_message = "La prova consente 1–10 richieste API al secondo."
  }
}

variable "api_burst_limit" {
  type    = number
  default = 10
  validation {
    condition     = var.api_burst_limit >= 5 && var.api_burst_limit <= 20 && floor(var.api_burst_limit) == var.api_burst_limit
    error_message = "Burst API intero di 5–20 richieste."
  }
}

variable "log_retention_days" {
  type    = number
  default = 1
  validation {
    condition     = contains([1, 3, 5, 7], var.log_retention_days)
    error_message = "Retention di 1, 3, 5 o 7 giorni per la prova."
  }
}
