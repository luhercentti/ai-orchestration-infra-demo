output "iam_user_arn" { value = aws_iam_user.this.arn }
output "credentials_secret_arn" {
  description = "Secrets Manager ARN holding the access key — do not log or expose"
  value       = aws_secretsmanager_secret.credentials.arn
}
