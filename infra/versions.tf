terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Real deployment: remote state in S3 + DynamoDB lock table, not local state.
  # backend "s3" {
  #   bucket         = "ai-orchestration-demo-tfstate"
  #   key            = "orchestrator/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
}
