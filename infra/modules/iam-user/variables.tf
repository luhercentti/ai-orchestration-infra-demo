variable "name" { description = "IAM username"; type = string }
variable "environment" { type = string }
variable "policy_arns" {
  description = "List of IAM policy ARNs to attach (e.g. arn:aws:iam::aws:policy/AdministratorAccess)"
  type        = list(string)
  default     = []
}
