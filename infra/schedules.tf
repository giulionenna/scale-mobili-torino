resource "aws_iam_role" "scheduler" {
  count                = var.enable_schedules ? 1 : 0
  name                 = "${var.prefix}-scheduler"
  permissions_boundary = var.runtime_permissions_boundary_arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "scheduler.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}

resource "aws_iam_role_policy" "scheduler" {
  count = var.enable_schedules ? 1 : 0
  name  = "${var.prefix}-scheduler"
  role  = aws_iam_role.scheduler[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Action = "lambda:InvokeFunction",
    Resource = [aws_lambda_function.backend["aggregate"].arn, aws_lambda_function.backend["collector"].arn]
  }] })
}

resource "aws_scheduler_schedule" "worker" {
  for_each            = var.enable_schedules ? { aggregate = "rate(5 minutes)", collector = "rate(4 hours)" } : {}
  name                = "${var.prefix}-${each.key}"
  schedule_expression = each.value
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.backend[each.key].arn
    role_arn = aws_iam_role.scheduler[0].arn
    input    = jsonencode({ execution_id = "<aws.scheduler.execution-id>" })
    retry_policy {
      maximum_event_age_in_seconds = 300
      maximum_retry_attempts       = 2
    }
  }
  depends_on = [aws_iam_role_policy.scheduler]
}
