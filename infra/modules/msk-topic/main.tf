resource "aws_msk_scram_secret_association" "placeholder" {
  # Kafka topic creation is handled via the Kafka admin API, not Terraform
  # resources directly. This module is a placeholder — in production use the
  # confluentinc/kafka Terraform provider or a custom Lambda-backed resource.
  # The cluster_arn variable is accepted so callers can reference the MSK cluster.
  count = 0 # no-op until a Kafka provider is wired in
}

# Topic metadata tracked in state so the workspace_key is idempotent.
resource "terraform_data" "topic_meta" {
  input = {
    name         = var.name
    partitions   = var.partitions
    retention_ms = var.retention_ms
    cluster_arn  = var.cluster_arn
  }
}
