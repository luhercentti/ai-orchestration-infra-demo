variable "name" { type = string }
variable "environment" { type = string }
variable "node_type" { type = string; default = "cache.t4g.micro" }
variable "subnet_ids" { type = list(string) }
variable "vpc_security_group_ids" { type = list(string) }
