import base64
import json

import pytest

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


def _invalid(call):
    with pytest.raises(ToolFailure) as caught:
        call()
    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_an_empty_position_is_invalid_argument():
    token = base64.urlsafe_b64encode(json.dumps({"c": "tjsp", "p": [], "f": "k"}).encode())

    _invalid(lambda: Cursor.decode(token.decode(), scopes=("tjsp",)))


@pytest.mark.parametrize("position", [(), (1, 2), ("x",), (-1,)])
def test_a_position_that_is_not_one_offset_is_invalid_argument(position):
    _invalid(lambda: Cursor("senado", position, "k").offset())


def test_a_single_non_negative_position_is_an_offset():
    assert Cursor("senado", (7,), "k").offset() == 7


@pytest.mark.parametrize("position", [(), (10,), ("x", 1), (1, 2), (1, "x", 2)])
def test_a_position_that_is_not_a_sort_position_is_invalid_argument(position):
    _invalid(lambda: Cursor("tjsp", position, "k").sort_position())


def test_a_timestamp_and_a_tiebreaker_are_a_sort_position():
    assert Cursor("tjsp", (10, "id-1"), "k").sort_position() == (10, "id-1")
