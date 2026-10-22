import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation_text import (
    Article,
    NormText,
    article_key,
    article_label,
    article_start,
    strip_annotations,
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


def test_strip_annotations_removes_a_trailing_note_and_the_space_before_it():
    text = "Art. 5º Todos são iguais. (Redação dada pela Lei nº 1, de 2001)"

    assert strip_annotations(text) == "Art. 5º Todos são iguais."


def test_strip_annotations_drops_a_line_made_only_of_a_note():
    text = "Art. 1º Texto.\n(Vide Decreto nº 12.174, de 2024)\n§ 1º Outro."

    assert strip_annotations(text) == "Art. 1º Texto.\n§ 1º Outro."


@pytest.mark.parametrize(
    "note",
    [
        "(Incluído pela Lei X)",
        "(Incluída pela Lei X)",
        "(Vigência)",
        "(Regulamento)",
        "(Renumerado pela Lei X)",
        "(Produção de efeito)",
        "(Vide Lei X (art. 2º))",
    ],
)
def test_strip_annotations_knows_each_prefix_in_any_case(note):
    assert strip_annotations(f"Art. 2º Texto. {note.upper()}") == "Art. 2º Texto."
    assert strip_annotations(f"Art. 2º Texto. {note}") == "Art. 2º Texto."


@pytest.mark.parametrize(
    "line",
    [
        "Art. 184. (Revogado pela Lei nº 10.695, de 2003)",
        "Art. 3º Texto (vetado).",
        "I - a (b)",
        "Art. 4º Veja (inciso II) deste artigo.",
    ],
)
def test_strip_annotations_keeps_revoked_and_unknown_parentheses(line):
    assert strip_annotations(line) == line


def test_strip_annotations_takes_the_vigencia_link_text_that_trails_a_note():
    text = "§ 1º Na mesma pena. (Incluído pela Lei nº 12.737, de 2012) Vigência"

    assert strip_annotations(text) == "§ 1º Na mesma pena."
    assert strip_annotations("Art. 9º Vigência") == "Art. 9º Vigência"
