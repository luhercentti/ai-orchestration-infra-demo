resource "aws_instance" "this" {
  ami                    = var.ami
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.vpc_security_group_ids
  key_name               = var.key_name != "" ? var.key_name : null

  # IMDSv2 required — disabling IMDSv1 closes a common SSRF attack surface.
  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    encrypted = true
  }

  tags = { Name = var.name, Environment = var.environment }
}
