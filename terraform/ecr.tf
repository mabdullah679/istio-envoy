resource "aws_ecr_repository" "service" {
  for_each             = toset(["service-a", "service-b"])
  name                 = "${var.name_prefix}-${each.key}"
  image_tag_mutability = "IMMUTABLE" # CI tags by git SHA, so a tag can never be silently re-pointed
  force_delete         = true        # lets `terraform destroy` remove repos that still hold images

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "service" {
  for_each   = aws_ecr_repository.service
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the 10 most recent images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}
