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
