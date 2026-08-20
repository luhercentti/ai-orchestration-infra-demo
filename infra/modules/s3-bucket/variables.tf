variable "name" { type = string }
variable "environment" { type = string }
variable "versioning" { type = bool; default = true }
variable "force_destroy" {
  type    = bool
  default = false # set true only for dev/test buckets
}
