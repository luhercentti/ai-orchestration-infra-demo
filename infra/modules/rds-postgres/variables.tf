variable "name" {
  description = "Resource name (from workspace_key, e.g. billing-staging-postgres)"
  type        = string
}

variable "environment" {
  type = string
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "subnet_ids" {
  type = list(string)
}

variable "vpc_security_group_ids" {
  type = list(string)
}
