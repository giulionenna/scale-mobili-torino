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
    error_message = "La prova AWS richiede prima la verifica di quote residue e budget zero."
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
  default = 2
  validation {
    condition     = var.reserved_concurrency >= 1 && var.reserved_concurrency <= 5
    error_message = "Il prototipo consente da 1 a 5 invocazioni concorrenti."
  }
}
