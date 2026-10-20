variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "name_prefix" {
  description = "Prefix on every resource name; the shared account has other projects in it."
  type        = string
  default     = "pf-istio-envoy"
}

variable "kubernetes_version" {
  type    = string
  default = "1.35"
}

variable "node_instance_type" {
  description = "Istio control plane + gateway + ratelimit + 4 JVMs need ~3 GiB of requests; t3.medium x2 is the measured floor (see README)."
  type        = string
  default     = "t3.medium"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "permissions_boundary_arn" {
  type    = string
  default = "arn:aws:iam::346208529954:policy/portfolio-ci-boundary"
}

variable "admin_principal_arns" {
  description = "Extra IAM principals granted cluster-admin through EKS access entries (for kubectl debugging)."
  type        = list(string)
  default     = ["arn:aws:iam::346208529954:role/managed/AccountFullAccessRole"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
