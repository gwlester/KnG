provider "aws" {
  region = var.aws_region
}

# CloudFront only accepts ACM certificates from us-east-1, regardless of
# which region the rest of the stack lives in.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
