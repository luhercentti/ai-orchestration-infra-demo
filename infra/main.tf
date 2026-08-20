locals {
  name = "${var.project_name}-${var.environment}"
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- Networking -------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.vpc_cidr

  azs             = data.aws_availability_zones.available.names
  private_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i + 3)]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "prod" # cost control for non-prod
  enable_dns_hostnames = true

  tags = local.tags
}

data "aws_availability_zones" "available" {
  state = "available"
}

# --- EKS: runs the orchestrator Deployment (see ../k8s) ----------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.name
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = var.eks_node_instance_types
      min_size       = 3
      max_size       = 10
      desired_size   = 3
    }
  }

  # Enables IRSA so the orchestrator pod gets a scoped IAM role instead of
  # broad node-level credentials (least-privilege for Secrets Manager/S3 access).
  enable_irsa = true

  tags = local.tags
}

# --- RDS Postgres: LangGraph checkpoint store --------------------------------
module "checkpoint_db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.name}-checkpoints"

  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.postgres_instance_class
  allocated_storage = 20

  db_name  = "langgraph"
  username = "langgraph"
  port     = 5432

  vpc_security_group_ids = [aws_security_group.checkpoint_db.id]
  subnet_ids              = module.vpc.private_subnets
  create_db_subnet_group  = true

  manage_master_user_password = true # stored in Secrets Manager automatically

  backup_retention_period = var.environment == "prod" ? 7 : 1
  deletion_protection     = var.environment == "prod"

  tags = local.tags
}

resource "aws_security_group" "checkpoint_db" {
  name_prefix = "${local.name}-checkpoint-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  tags = local.tags
}

# --- ElastiCache Redis: streaming/pub-sub state ------------------------------
resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_cluster" "streaming" {
  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = local.tags
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  tags = local.tags
}

# --- Secrets: model API keys, referenced by the orchestrator pod via IRSA ---
resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${local.name}/openai-api-key"
  tags = local.tags
}

# --- IRSA: least-privilege IAM role for the orchestrator pod ----------------
module "orchestrator_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name}-orchestrator"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["ai-orchestration-demo:orchestrator"]
    }
  }

  # Scoped to only what the orchestrator needs — no wildcard resource access.
  role_policy_arns = {
    secrets = aws_iam_policy.orchestrator_secrets_read.arn
  }

  tags = local.tags
}

resource "aws_iam_policy" "orchestrator_secrets_read" {
  name = "${local.name}-orchestrator-secrets-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.openai_api_key.arn,
          module.checkpoint_db.db_instance_master_user_secret_arn,
        ]
      }
    ]
  })
}
