import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication_query import (
    MAX_EXCLUSIONS,
    MAX_GROUPS,
    normalized_words,
    parse_query,
)


def _invalid(query: str) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        parse_query(query)
    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    return caught.value


def test_a_space_is_an_and_inside_one_group():
    (group,) = parse_query("  recurso especial  ")

    assert [t.text for t in group.required] == ["recurso", "especial"]
    assert group.excluded == ()


def test_or_splits_groups():
    groups = parse_query('dano moral OR "tema 1234" OR -ausente consumidor')

    assert [[t.text for t in g.required] for g in groups] == [
        ["dano", "moral"],
        ["tema 1234"],
        ["consumidor"],
    ]
    assert [t.text for t in groups[2].excluded] == ["ausente"]


def test_a_quoted_phrase_is_one_term_and_a_quoted_exclusion_is_supported():
    (group,) = parse_query('"dano moral" -"erro médico"')

    assert group.required[0].words == ("dano", "moral")
    assert group.excluded[0].words == ("erro", "medico")


def test_the_dispatched_term_is_the_longest_phrase():
    (group,) = parse_query('indenizatoria "dano moral" "ação"')

    assert group.dispatched.text == "dano moral"


def test_without_a_phrase_the_dispatched_term_is_the_longest_word():
    (group,) = parse_query("de recurso especial extraordinario")

    assert group.dispatched.text == "extraordinario"


def test_a_phrase_shorter_than_5_characters_is_not_dispatched():
    (group,) = parse_query('"de a" recurso')

    assert group.dispatched.text == "recurso"


@pytest.mark.parametrize("query", ["", "   ", "abcd", "-recurso", "de ao OR recurso", '"abc"'])
def test_a_group_without_a_dispatchable_term_is_invalid(query):
    assert "5 characters" in _invalid(query).message or "empty" in _invalid(query).message


@pytest.mark.parametrize(
    "query",
    [
        'recurso "especial',
        "OR recurso",
        "recurso OR",
        "recurso OR OR especial",
        "recurso -",
        '""',
        "recurso AND especial",
        "recurso NOT especial",
        "recurso*",
        "recurso §",
    ],
)
def test_malformed_input_explains_itself(query):
    failure = _invalid(query)

    assert failure.message


def test_the_limits_on_groups_and_exclusions():
    _invalid(" OR ".join(["recurso"] * (MAX_GROUPS + 1)))
    _invalid("recurso " + " ".join(f"-excl{i}" for i in range(MAX_EXCLUSIONS + 1)))
    parse_query("recurso " + " ".join(f"-excl{i}" for i in range(MAX_EXCLUSIONS)))


def test_the_exclusion_limit_counts_every_group():
    exclusions = " ".join(f"-excl{i}" for i in range(MAX_EXCLUSIONS // 2 + 1))

    _invalid(f"recurso {exclusions} OR especial {exclusions}")


def test_lowercase_or_is_a_word():
    (group,) = parse_query("recurso or especial")

    assert [t.text for t in group.required] == ["recurso", "or", "especial"]


def test_the_local_filter_requires_the_other_words_by_prefix_ignoring_case_and_accents():
    (group,) = parse_query("recurso ESPECIAL")

    assert group.matches(normalized_words("Recursos interpostos"))
    assert not group.matches(normalized_words("Ordinários interpostos"))


def test_a_prefix_is_of_the_word_not_of_any_substring():
    (group,) = parse_query("extraordinario curso")

    assert not group.matches(normalized_words("recurso extraordinario"))


def test_a_phrase_matches_adjacent_words_in_order():
    (group,) = parse_query('"dano moral" indenizatoria')

    assert group.matches(normalized_words("Danos morais e indenizatória"))
    assert not group.matches(normalized_words("moral dano"))
    assert not group.matches(normalized_words("dano material e moral"))


def test_an_excluded_term_drops_the_text_and_an_absent_one_does_not():
    (group,) = parse_query("recurso especial -honorários")

    assert not group.matches(normalized_words("recurso especial sobre honorarios"))
    assert group.matches(normalized_words("recurso especial sobre custas"))


def test_an_excluded_term_matches_by_prefix_too():
    (group,) = parse_query("recurso especial -honorario")

    assert not group.matches(normalized_words("recurso especial sobre honorários"))


def test_the_dispatched_term_is_left_to_the_source():
    (group,) = parse_query("recurso especial")

    assert group.matches(normalized_words("recurso"))


def test_claims_asks_the_source_term_exactly_and_the_rest_locally():
    (group,) = parse_query("recurso especial")

    assert group.claims(normalized_words("especial recurso"))
    assert not group.claims(normalized_words("especiais recurso"))
    assert not group.claims(normalized_words("especial"))


def test_without_dispatch_nothing_is_sent_and_short_terms_are_allowed():
    (group,) = parse_query("de dano -outro", dispatch=False)

    assert group.dispatched is None
    assert group.matches(("de", "dano")) and not group.matches(("dano", "outro"))


def test_without_dispatch_an_empty_query_matches_everything():
    (group,) = parse_query("  ", dispatch=False)

    assert group.matches(("qualquer", "coisa"))


def test_without_dispatch_an_empty_or_group_is_still_invalid():
    with pytest.raises(ToolFailure):
        parse_query("dano OR", dispatch=False)
