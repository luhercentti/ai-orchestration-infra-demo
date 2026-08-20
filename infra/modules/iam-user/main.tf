resource "aws_iam_user" "this" {
  name = var.name
  tags = { Environment = var.environment }
}

resource "aws_iam_user_policy_attachment" "this" {
  for_each   = toset(var.policy_arns)
  user       = aws_iam_user.this.name
  policy_arn = each.value
}

# Programmatic access key — stored in Secrets Manager, not in Terraform state.
resource "aws_iam_access_key" "this" {
  user = aws_iam_user.this.name
}

resource "aws_secretsmanager_secret_version" "credentials" {
  secret_id = aws_secretsmanager_secret.credentials.id
  secret_string = jsonencode({
    access_key_id     = aws_iam_access_key.this.id
    secret_access_key = aws_iam_access_key.this.secret
  })
}

resource "aws_secretsmanager_secret" "credentials" {
  name = "iam/${var.name}/credentials"
}
