# Research: AWS deployment options for a remote MCP container

Issue: #5 (part of map #1). Researched 2026-10-17. Primary sources only (AWS docs, MCP specification). Prices are AWS's us-east-1 reference rates; AWS pages did not expose sa-east-1 rates, so those must be checked in the AWS Pricing Calculator.

## Question

Compare Lambda (with Web Adapter), ECS Fargate, App Runner (and anything better) for a low-traffic, streamable-HTTP MCP container in sa-east-1: session/SSE support, cold starts, cost at low traffic, secrets, API-key auth in front, IaC options.

## Key findings

1. **App Runner is not an option for a new account.** "AWS App Runner is no longer open to new customers"; AWS "do[es] not plan to introduce new features" and recommends ECS Express Mode as the replacement. [App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
2. **ECS Express Mode is the "better" candidate AWS itself points to.** Given an image plus two IAM roles, it provisions "a Fargate-based ECS service with a unique accessible URL, load balancer with SSL/TLS, auto scaling policies, monitoring, and networking components." No extra charge; you pay for Fargate, the ALB, CloudWatch and data transfer. It shares ALBs across Express services with the same networking. IaC: CloudFormation, Terraform, CLI, SDKs. Available wherever ECS and Fargate are. [Express Mode overview](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
3. **The MCP spec does not require long-lived streams or sessions.** Sessions are optional (a server "MAY assign a session ID"); a POST may be answered with a single `application/json` response instead of SSE; the standalone GET stream may be refused with 405. So a stateless server (no `Mcp-Session-Id`, JSON responses) is spec-compliant and fits Lambda. [MCP transports, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
4. **API Gateway API keys are not an authentication mechanism.** AWS: "Don't use API keys for authentication or authorization"; usage-plan quotas are best-effort. API keys and usage plans are REST API features. Use a Lambda authorizer (or check the key in the app/ALB) instead. [Usage plans and API keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)

## MCP transport requirements that drive the choice

From the [MCP transports spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports):

- One MCP endpoint supporting POST and GET.
- POST responses are either `text/event-stream` or `application/json`; clients MUST support both. A server using SSE SHOULD NOT close the stream before sending the response.
- GET to open a server-to-client stream is optional: the server MUST return SSE or 405.
- Sessions (`Mcp-Session-Id`) are optional; if issued, requests without it SHOULD get 400, an expired session MUST get 404 (client re-initializes).
- Servers MUST validate `Origin` and SHOULD authenticate all connections.
- Resumability (`Last-Event-ID`) is optional.

Implication: for this project (read-only judicial lookups, no server-initiated messages), a stateless JSON-response mode is enough. SSE is only needed for long tool calls with progress. I could not confirm FastMCP's exact flag names from a primary source in this session (the Python SDK README fetched did not document `stateless_http`/`json_response`); verify in the SDK docs during implementation.

## Option comparison

| Criterion | Lambda + Web Adapter | ECS Fargate (plain) | ECS Express Mode | App Runner |
|---|---|---|---|---|
| Available to new accounts | Yes | Yes | Yes | No (closed to new customers) |
| Stateless JSON MCP | Works | Works | Works | n/a |
| SSE / streaming | Needs response streaming (see below) | Native | Native (ALB) | n/a |
| Idle cost | Pay per use, free tier | Fargate task + ALB always on | Same as Fargate + ALB (min tasks shown as 1 in AWS CLI example) | n/a |
| Cold start | Yes (container init) | None while task is running | None while task is running | n/a |
| Front-door auth | Function URL: only `AWS_IAM` or `NONE`; API key must be checked in the app or an authorizer | ALB has no API-key feature; check in app | Same as Fargate | n/a |
| Secrets | Env vars / Secrets Manager (not researched in depth) | `secrets` in task definition from Secrets Manager | Same | n/a |
| IaC | SAM, CloudFormation, Terraform, CDK | CloudFormation, Terraform, CDK | CloudFormation, Terraform, CLI | n/a |

### Lambda with Lambda Web Adapter

- Web Adapter supports Function URLs, API Gateway REST/HTTP and ALB triggers, and response streaming via `AWS_LWA_INVOKE_MODE=response_stream` (default `buffered`). Compression is not available in streaming mode. [aws-lambda-web-adapter](https://github.com/awslabs/aws-lambda-web-adapter)
- Lambda "supports response streaming on Node.js managed runtimes. For other languages, including Python, you can use a custom runtime ... or the Lambda Web Adapter." Streaming works through Function URLs, `InvokeWithResponseStream`, and API Gateway proxy integration. Streamed responses are billed for full duration even if the client disconnects. Function URLs do not support streaming inside a VPC. Streaming "is not yet available in all AWS Regions"; sa-east-1 availability was not verified here. [Lambda response streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html)
- API Gateway streams Lambda only through `InvokeWithResponseStream` with a special output format (metadata JSON, 8 null-byte delimiter); Web Adapter output would need to match, which is unverified. [API Gateway Lambda streaming](https://docs.aws.amazon.com/apigateway/latest/developerguide/response-transfer-mode-lambda.html)
- Function URL auth is `AWS_IAM` (SigV4) or `NONE` (public). With `NONE`, "anyone who has your function URL can invoke your function", so the API key check must live in the server code. MCP clients generally cannot SigV4-sign, so `AWS_IAM` is unsuitable for agents. [Function URL auth](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)
- Cost (us-east-1): $0.20 per 1M requests, $0.0000166667 per GB-second (x86), always-free 1M requests and 400,000 GB-seconds per month; streaming $0.008/GB after 100 GB free. [Lambda pricing](https://aws.amazon.com/lambda/pricing/)

### ECS Fargate and ECS Express Mode

- Fargate (us-east-1): about $0.0405 per vCPU-hour and $0.0044 per GB-hour on x86, about $0.0324 and $0.0036 on ARM; per-second billing with a 1-minute minimum. [Fargate pricing](https://aws.amazon.com/fargate/pricing/)
- ALB (us-east-1): $0.0225 per hour plus $0.008 per LCU-hour, plus public IPv4 charges. [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
- Rough order of magnitude (computed from the above, not an AWS quote): one 0.25 vCPU / 0.5 GB ARM task is about $7 to $8 per month and the ALB about $16 to $17 per month before LCU and IPv4, so the always-on floor is roughly $25 per month at us-east-1 rates. Lambda at low traffic stays inside the free tier.
- Secrets: the task definition `secrets` field injects Secrets Manager values as env vars at task start; they are not refreshed until a new task starts; the task execution role needs Secrets Manager permission. [ECS Secrets Manager env vars](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html)
- Express Mode deploy automation: AWS publishes a GitHub Action `amazon-ecs-deploy-express-service`; provisioning "typically takes 3-5 minutes". [App Runner migration guide](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)

## Tentative recommendation (for the decision ticket, not a decision)

- **Cheapest viable:** Lambda + Web Adapter behind a Function URL (`NONE`), server in stateless/JSON mode, API key checked in the app against a Secrets Manager/SSM-backed value, with a small cold start accepted. Fits "low traffic, minimal cost". Risk: streaming/SSE and sa-east-1 feature availability.
- **Most conventional:** ECS Express Mode (Fargate + ALB). Native SSE and sessions, no cold start, one container artifact, but about a $25/month floor.
- **Rule out:** App Runner (closed to new customers).
- The container stays the single artifact in both cases (matches map notes); Dockerfile with Web Adapter as a layer can still run locally and on Fargate.

## Not verified / open questions

- sa-east-1 prices for Lambda, Fargate and ALB, and whether Lambda response streaming is available in sa-east-1.
- Measured Lambda container cold start for a Python FastMCP image (AWS pricing/streaming pages say nothing about it).
- Whether ECS Express Mode can scale to zero (the sources show only `minTaskCount` examples of 1).
- ALB idle timeout behaviour for long SSE streams.
- Exact FastMCP stateless/JSON-response options (check the Python SDK docs).
- WAF/rate limiting options in front of a Function URL (not researched).
