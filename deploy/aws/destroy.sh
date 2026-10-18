#!/usr/bin/env bash
# Removes everything deploy/aws/ created. Run from the checkout that ran deploy.sh.
set -euo pipefail

export AWS_PAGER=""
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TFVARS="$HERE/terraform.tfvars"
cd "$HERE"

[[ -f "$TFVARS" ]] || { echo "No $TFVARS: nothing to destroy from this checkout."; exit 1; }
[[ -f terraform.tfstate ]] || { echo "No terraform.tfstate here: Terraform cannot know what was deployed."; exit 1; }
IDENTITY="$(aws sts get-caller-identity --query Arn --output text)" \
  || { echo "No AWS credentials. Run 'aws configure' or 'aws sso login', then re-run."; exit 1; }

NAME="$(terraform output -raw function_name)"
echo "AWS identity: $IDENTITY"
echo "This permanently deletes the Lambda '$NAME', its Function URL, log group and logs,"
echo "saved queries, IAM role and the ECR repository with every image."
terraform plan -destroy -input=false -var-file="$TFVARS" | grep -E "will be destroyed|Plan:" || true
read -r -p "Type the deployment name ($NAME) to confirm: " reply
[[ "$reply" == "$NAME" ]] || { echo "Not confirmed. Nothing was deleted."; exit 1; }

# force_delete lives in the state: record it first so a repository that already holds images can go.
terraform apply -input=false -var-file="$TFVARS" -target=aws_ecr_repository.image -auto-approve >/dev/null
terraform destroy -input=false -var-file="$TFVARS" -auto-approve
echo "Destroyed. terraform.tfvars and terraform.tfstate are still here; delete them if you are done."
