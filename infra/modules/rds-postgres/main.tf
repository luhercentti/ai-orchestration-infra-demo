resource "aws_db_instance" "this" {
  identifier        = var.name
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage

  db_name  = replace(var.name, "-", "_")
  username = "app"
  port     = 5432

  manage_master_user_password    = true
  db_subnet_group_name           = aws_db_subnet_group.this.name
  vpc_security_group_ids         = var.vpc_security_group_ids
  backup_retention_period        = var.environment == "prod" ? 7 : 1
  deletion_protection            = var.environment == "prod"
  skip_final_snapshot            = var.environment != "prod"

  tags = { Name = var.name, Environment = var.environment }
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}
