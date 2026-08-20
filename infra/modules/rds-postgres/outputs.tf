output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret holding the master password"
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
