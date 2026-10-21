import base64
from datetime import date

import pytest

from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication import PublicationRef

REF = PublicationRef("tjsp", date(2026, 10, 15), CnjNumber("12345677620258260100"), "h|1")


def _encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def test_an_encoded_ref_decodes_to_itself_even_with_a_bar_in_the_hash():
    assert PublicationRef.decode(REF.encode()) == REF


@pytest.mark.parametrize(
    "token",
    [
        "not base64 !!",
        _encode("tjsp|2026-10-15|12345677620258260100"),
        _encode("tjsp|15/10/2026|12345677620258260100|h1"),
        _encode("tjsp|2026-10-15|123|h1"),
        _encode("tjsp|2026-10-15|12345677620258260100|"),
        _encode("|2026-10-15|12345677620258260100|h1"),
    ],
)
def test_a_malformed_token_is_invalid_argument(token):
    with pytest.raises(ToolFailure) as caught:
        PublicationRef.decode(token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
