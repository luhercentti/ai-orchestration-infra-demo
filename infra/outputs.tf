output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "checkpoint_db_endpoint" {
  value = module.checkpoint_db.db_instance_endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.streaming.cache_nodes[0].address
}

output "orchestrator_irsa_role_arn" {
  value = module.orchestrator_irsa.iam_role_arn
}
