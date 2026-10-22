"""The portability boundary (ADR 0003): the package is the container, never AWS."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).parents[3] / "juris_bridge_mcp"
AWS_MODULES = {"boto3", "botocore", "aioboto3", "awslambdaric", "mangum", "aws_lambda_powertools"}


def _imported_roots(source: str) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_package_never_imports_an_aws_sdk_or_lambda_runtime():
    imported = {path: _imported_roots(path.read_text()) for path in PACKAGE.rglob("*.py")}
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(roots & AWS_MODULES)
        for path, roots in imported.items()
        if roots & AWS_MODULES
    }

    assert offenders == {}


def test_the_package_does_not_read_lambda_invocation_events():
    markers = ("lambda_handler", "requestContext", "AWS_LAMBDA_RUNTIME_API")
    offenders = [
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if any(marker in path.read_text() for marker in markers)
    ]

    assert offenders == []
