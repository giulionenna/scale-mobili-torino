# Configurazione pubblica di esempio; questo file non viene caricato automaticamente.
# budget_reviewed resta false fino alla verifica economica successiva.
prefix                = "scale-mobili-prototype"
region                = "eu-south-1"
frontend_url          = "https://frontend.example"
enable_schedules      = false
budget_reviewed       = false
dynamodb_billing_mode = "PAY_PER_REQUEST"
reserved_concurrency  = 1
api_rate_limit        = 2
api_burst_limit       = 10
log_retention_days    = 1
# Il segreto viene passato come TF_VAR_cursor_secret, mai salvato in questo file.
