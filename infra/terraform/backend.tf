# Configure remote state before using this module from CI or a shared team
# environment. Backend settings cannot use Terraform variables, so keep the
# concrete bucket/table names environment-specific.
#
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE_WITH_STATE_BUCKET"
#     key            = "tango/sandbox/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "REPLACE_WITH_LOCK_TABLE"
#     encrypt        = true
#   }
# }
