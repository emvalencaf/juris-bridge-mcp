#!/usr/bin/env bash
# Guided deploy of the Reference deployment (ADR 0003): ECR repo -> image -> Lambda + Function URL.
# Run from anywhere: deploy/aws/wizard.sh. Re-running is safe; every step is idempotent.
set -euo pipefail

# AWS CLI v2 pipes output through `less`, which would stop the wizard at "(END)".
export AWS_PAGER=""

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TFVARS="$HERE/terraform.tfvars"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ask() { # ask VAR "prompt" default
  local reply
  read -r -p "$2 [${3:-}]: " reply
  printf -v "$1" '%s' "${reply:-${3:-}}"
}
confirm() { local r; read -r -p "$1 [y/N]: " r; [[ "$r" =~ ^[Yy]$ ]]; }

say "1/6 Prerequisites"
for tool in aws terraform docker openssl; do
  command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }
done
echo "AWS identity: $(aws sts get-caller-identity --query Arn --output text)" \
  || { echo "No AWS credentials. Run 'aws configure' or 'aws sso login', then re-run."; exit 1; }

say "2/6 Settings"
tfvar() { grep "^$1 " "$TFVARS" | cut -d'"' -f2; } # read a string value back from terraform.tfvars
tf_escape() { local v="${1//\\/\\\\}"; printf '%s' "${v//\"/\\\"}"; }
if [[ -f "$TFVARS" ]] && ! confirm "Rewrite $TFVARS?"; then
  REGION="$(tfvar region)"; ENVIRONMENT="$(tfvar environment)"; ARCH="$(tfvar architecture)"
  echo "Keeping $TFVARS: region $REGION, environment $ENVIRONMENT, architecture $ARCH."
else
  ask REGION "AWS region" "${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
  ask ENVIRONMENT "Deployment name suffix" "prod"
  case "$(uname -m)" in aarch64|arm64) ARCH=arm64 ;; *) ARCH=x86_64 ;; esac
  ask ARCH "Lambda architecture, must match the machine building the image (arm64 or x86_64)" "$ARCH"
  API_KEYS="$(openssl rand -hex 32)"
  echo "Generated an API key for your MCP clients (shown once, also saved in terraform.tfvars):"
  echo "  $API_KEYS"
  read -r -s -p "DataJud API key (the CNJ public key): " DATAJUD_KEY; echo
  (umask 077; cat >"$TFVARS" <<TFV
region          = "$REGION"
environment     = "$ENVIRONMENT"
architecture    = "$ARCH"
api_keys        = "$API_KEYS"
datajud_api_key = "$(tf_escape "$DATAJUD_KEY")"
commit_hash     = "$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
TFV
  )
fi

cd "$HERE"
terraform init -input=false

say "3/6 Registry"
terraform apply -input=false -var-file="$TFVARS" -target=aws_ecr_repository.image -auto-approve
REPO="$(terraform output -raw ecr_repository_url)"

say "4/6 Image ($REPO)"
PLATFORM="linux/${ARCH/x86_64/amd64}"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPO%%/*}"
# --provenance=false: Lambda rejects the multi-manifest index buildx adds by default.
docker build --provenance=false --platform "$PLATFORM" -f "$ROOT/deploy/aws/Dockerfile" \
  -t "$REPO:latest" "$ROOT"
docker push "$REPO:latest"

say "5/6 Function, Function URL, logs"
confirm "Create or update the Lambda in $REGION now?" || { echo "Stopped before the Lambda."; exit 0; }
terraform apply -input=false -var-file="$TFVARS"
FUNCTION="$(terraform output -raw function_name)"
# A new image under the same tag is not picked up by itself.
aws lambda update-function-code --region "$REGION" \
  --function-name "$FUNCTION" --image-uri "$REPO:latest" >/dev/null
aws lambda wait function-updated --region "$REGION" --function-name "$FUNCTION"

say "6/6 Smoke test"
URL="$(terraform output -raw mcp_url)"
KEY="$(grep '^api_keys' "$TFVARS" | cut -d'"' -f2 | cut -d, -f1)"
echo "No key  -> $(curl -s -m 60 -o /dev/null -w '%{http_code}' -X POST "$URL") (expect 401)"
echo "GET     -> $(curl -s -m 60 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $KEY" "$URL") (expect 405)"
curl -s -m 60 -o /dev/null -w 'Cold start (initialize) -> %{http_code} in %{time_total}s\n' -X POST "$URL" \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"wizard","version":"0"}}}' || echo "Cold start request failed (timeout or network)."

say "Done"
echo "MCP URL: $URL"
echo "Logs Insights queries are saved under the log group $(terraform output -raw log_group)."
echo "Record the cold start and source reachability in docs/research/aws-reference-verification.md."
