terraform {
  required_version = ">= 1.10.0"

  # The state bucket is created once by hand (see Prompts/AWS_Deployment.md
  # step 0) -- Terraform can't manage the bucket that holds its own state.
  backend "s3" {
    bucket       = "kng-consulting-tfstate-734677164811"
    key          = "kng-site/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}
