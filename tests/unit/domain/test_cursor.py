import base64
import json

import pytest

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


def test_round_trips_court_position_and_filters():
    cursor = Cursor(scope="tjsp", position=(1717858523378, "TJSP_G1_1"), filters_key="abc")

    assert Cursor.decode(cursor.encode(), scopes=("tjsp",)) == cursor


def test_token_is_opaque_url_safe_text():
    token = Cursor(scope="trf1", position=(1, "x"), filters_key="k").encode()

    assert token.isascii() and "=" not in token and "trf1" not in token


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not a cursor",
        base64.urlsafe_b64encode(b"[1, 2]").decode(),
        base64.urlsafe_b64encode(json.dumps({"c": "tjsp"}).encode()).decode(),
        base64.urlsafe_b64encode(
            json.dumps({"c": "tjsp", "p": [True, "x"], "f": "k"}).encode()
        ).decode(),
        base64.urlsafe_b64encode(json.dumps({"c": "tjsp", "p": [], "f": "k"}).encode()).decode(),
        base64.urlsafe_b64encode(
            json.dumps({"c": "nope", "p": [1, "x"], "f": "k"}).encode()
        ).decode(),
    ],
)
def test_a_malformed_token_is_invalid_argument(token):
    with pytest.raises(ToolFailure) as caught:
        Cursor.decode(token, scopes=("tjsp",))

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_a_cursor_decodes_only_for_the_scopes_it_is_asked_for():
    token = Cursor(scope="senado", position=(10,), filters_key="k").encode()

    assert Cursor.decode(token, scopes=("senado",)).position == (10,)
    with pytest.raises(ToolFailure) as caught:
        Cursor.decode(token, scopes=("tjsp",))
    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize("position", [(), (1, 2), ("x",), (-1,)])
def test_a_position_that_is_not_one_offset_is_invalid_argument(position):
    with pytest.raises(ToolFailure) as caught:
        Cursor(scope="senado", position=position, filters_key="k").offset()

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_a_single_non_negative_position_is_an_offset():
    assert Cursor(scope="senado", position=(7,), filters_key="k").offset() == 7
