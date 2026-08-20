variable "name" { type = string }
variable "environment" { type = string }
variable "cluster_arn" { description = "MSK cluster ARN"; type = string }
variable "partitions" { type = number; default = 6 }
variable "retention_ms" { type = number; default = 604800000 } # 7 days
