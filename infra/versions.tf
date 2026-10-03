terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# Credentials come from the environment (AWS_PROFILE=terraform-admin), never from code.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project    = "db-delay-tracker"
      managed_by = "terraform"
    }
  }
}
