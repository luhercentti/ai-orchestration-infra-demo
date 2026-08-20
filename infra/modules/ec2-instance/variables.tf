variable "name" { type = string }
variable "environment" { type = string }
variable "ami" { description = "AMI ID (region-specific)"; type = string }
variable "instance_type" { type = string; default = "t3.micro" }
variable "subnet_id" { type = string }
variable "vpc_security_group_ids" { type = list(string) }
variable "key_name" { description = "EC2 key pair name for SSH access"; type = string; default = "" }
