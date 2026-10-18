import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation_text import (
    Article,
    NormText,
    article_key,
    article_label,
    article_start,
)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Art. 5º", "5"),
        ("art 5", "5"),
        ("5", "5"),
        (" Artigo 5° ", "5"),
        ("Art. 121-A", "121-a"),
        ("121 a", "121-a"),
        ("Art. 1.045", "1045"),
        ("Art. único", "unico"),
        ("Único", "unico"),
    ],
)
def test_an_article_reference_has_one_key(raw, key):
    assert article_key(raw) == key


@pytest.mark.parametrize("raw", ["", "section 5", "Art.", "§ 1º", "Art. 5º, caput"])
def test_a_non_reference_is_invalid(raw):
    with pytest.raises(ToolFailure) as caught:
        article_key(raw)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize(
    ("key", "label"),
    [("5", "Art. 5º"), ("10", "Art. 10"), ("121-a", "Art. 121-A"), ("unico", "Art. único")],
)
def test_the_label_follows_the_brazilian_convention(key, label):
    assert article_label(key) == label


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("Art. 1º Esta Lei estabelece", "1"),
        ("Art 187. (Revogado pela Lei nº 9.279)", "187"),
        ("Art. 185 - (Revogado)", "185"),
        ("Art. 12 - A administração", "12"),
        ("Art. 12-A. O prazo", "12-a"),
        ("Art. único. Revogam-se", "unico"),
        ("Artefatos de lei", None),
        ("§ 1º Não são abrangidas", None),
        ("“Art. 5º Texto citado”", None),
    ],
)
def test_a_line_opens_an_article_only_when_it_starts_with_one(line, key):
    assert article_start(line) == key


def test_find_article_prefers_the_first_unflagged_occurrence():
    text = NormText(
        "",
        (
            Article("2", "old", ("superseded",)),
            Article("2", "new"),
            Article("3", "three"),
        ),
        "u",
    )

    assert text.find_article("2") == (text.articles[1], 2)
    assert text.find_article("3") == (text.articles[2], 1)
    assert text.find_article("9") == (None, 0)


def test_find_article_falls_back_to_the_first_when_all_are_flagged():
    text = NormText("", (Article("2", "a", ("revoked",)), Article("2", "b", ("superseded",))), "u")

    assert text.find_article("2")[0].text == "a"
