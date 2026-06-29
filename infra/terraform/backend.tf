# Bootstrap the remote-state bucket and lock table first from:
#   ../terraform-state
#
# Backend settings cannot use Terraform variables, so keep concrete names here.
# Current bootstrap output:
#   bucket         = "tango-test-569813798269-us-east-1-tf-state"
#   dynamodb_table = "tango-test-tf-locks"
#
terraform {
  backend "s3" {
    bucket       = "tango-test-569813798269-us-east-1-tf-state"
    key          = "tango/sandbox/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
