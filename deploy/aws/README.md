# AWS Reference deployment

A stateless Lambda container image with the [Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)
in `buffered` mode behind a Function URL (auth `NONE`; the Bearer key is checked in the app).
See [ADR 0003](../../docs/adr/0003-stateless-lambda-reference-deployment.md). This directory
is the only place that knows AWS: the server and its modules never import an AWS SDK or read a
Lambda event.

## Deploy

Needs `aws` (with credentials), `terraform`, `docker` and `openssl`.

```bash
deploy/aws/wizard.sh
```

It creates the ECR repository, builds and pushes `deploy/aws/Dockerfile`, applies Terraform and
smoke-tests the URL. It generates the API key (shown once) and writes git-ignored
`terraform.tfvars`. Prefer plain Terraform? Copy `example.tfvars`, create the ECR repository
first (`terraform apply -target=aws_ecr_repository.image`), push the image, then `terraform apply`.

## What Terraform creates

- Lambda function (container image, `arm64` by default, 512 MB, 60 s) and Function URL.
- Log group with 30-day retention and four saved Logs Insights queries (slowest requests,
  errors, calls by tool, cold starts) over the [wide events](../../docs/adr/0004-wide-event-logging-to-stdout.md).
- `api_keys` and `datajud_api_key` are sensitive variables turned into Lambda environment
  variables. They are readable in the Terraform state and in the Lambda console: keep the state
  private. Moving them to Secrets Manager is the documented best-practice follow-up.

The region defaults to `us-east-1`; set `region` to change it. For prices use the
[AWS Pricing Calculator](https://calculator.aws/).

## Verification

Cold start, reachability of the Brazilian government sources from `us-east-1` and the
FastMCP stateless flags are recorded in
[`docs/research/aws-reference-verification.md`](../../docs/research/aws-reference-verification.md).
