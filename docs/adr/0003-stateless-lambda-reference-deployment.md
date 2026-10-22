# Stateless Lambda as the AWS reference, with the container as the portability boundary

The AWS reference deployment is a Lambda container image with the Lambda Web
Adapter behind a Function URL (auth `NONE`), provisioned with Terraform. The
server runs FastMCP stateless with JSON responses (no `Mcp-Session-Id`, no SSE,
GET answers 405), which the MCP transport spec allows and which every tool
(short, read-only lookups) fits. The Web Adapter runs in `buffered` mode.

API-key auth lives in the app, as an ASGI middleware (`Authorization: Bearer`,
constant-time compare, keys from a comma-separated config list), because a
Function URL only offers `AWS_IAM` or `NONE`, an ALB has no API-key feature and
API Gateway API keys are not an authentication mechanism. The server refuses to
start with no key configured.

The portability boundary is "the container plus environment variables": server
and modules never import AWS SDKs or read Lambda events, and AWS-only code
(Terraform, the Web Adapter stage, the deploy wizard) lives under `deploy/aws/`.
The same image runs under `docker run`, `uv run` and Fargate. Secrets are
tiered (local `.env`, AWS free tier as sensitive Terraform variables turned into
Lambda environment variables, AWS best practice as a documented follow-up); the
app only ever reads environment variables. The default region is `us-east-1`
and configurable. Docs carry no prices, only pointers to the AWS Pricing
Calculator.

## Considered

- **ECS Express Mode (Fargate + ALB):** native SSE and no cold start, but an
  always-on cost floor. Kept as a later expansion with the same image.
- **App Runner:** closed to new customers.
- **API Gateway API keys or `AWS_IAM` on the Function URL:** not authentication,
  and MCP clients cannot SigV4-sign.
- **WAF:** not free, and it cannot attach to a Function URL directly (it would
  need CloudFront in front). Documented as hardening, not in the MVP.

## Consequences

The in-memory cache lives per warm execution environment only. Cold start,
`sa-east-1` and `us-east-1` source reachability (possible geo-blocking of
Brazilian government sites) and the FastMCP stateless flags are verified at
implementation time.
