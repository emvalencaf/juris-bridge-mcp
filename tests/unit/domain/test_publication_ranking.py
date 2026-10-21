import time

from juris_bridge_mcp.domain.publication_query import parse_query
from juris_bridge_mcp.domain.publication_ranking import query_terms, rank


def _rank(query: str, *texts: str):
    return rank(query_terms(parse_query(query)), texts)


def test_a_text_with_more_of_the_terms_scores_higher():
    both, one, none = _rank(
        "dano moral",
        "Condeno ao dano moral",
        "Condeno ao dano material",
        "Nada a ver com isso",
    )

    assert both.score > one.score > none.score == 0


def test_a_rarer_term_in_the_page_weighs_more():
    filler = "x " * 10
    with_rare, with_common, _ = _rank(
        "ressarcimento recurso",
        f"Recurso ressarcimento {filler}",
        f"Recurso admitido {filler}",
        f"Recurso negado {filler}",
    )

    assert with_rare.score > with_common.score > 0


def test_an_ementa_mentioned_in_the_body_is_not_boosted():
    filler = "palavra " * 400
    heading, mention = _rank(
        "consumidor",
        f"EMENTA: consumidor {filler}",
        f"{filler}conforme a ementa consumidor {'palavra ' * 20}",
    )

    assert heading.score > mention.score


def test_repeating_a_term_adds_less_each_time():
    filler = "palavra " * 40
    once, twice, thrice = _rank(
        "consumidor",
        f"consumidor {filler}",
        f"consumidor consumidor {filler}",
        f"consumidor consumidor consumidor {filler}",
        "outro texto " * 20,
    )[:3]

    assert once.score < twice.score < thrice.score
    assert thrice.score - twice.score < twice.score - once.score


def test_a_long_text_saturates_instead_of_winning_on_length():
    short, long = _rank("consumidor", "consumidor " * 3, ("consumidor " + "x " * 500) * 3)

    assert short.score > long.score


def test_the_start_and_the_ementa_weigh_more_than_the_body():
    filler = "palavra " * 400
    head, ementa, body, other = _rank(
        "consumidor",
        f"consumidor {filler}",
        f"{'palavra ' * 200}EMENTA: consumidor {'palavra ' * 200}",
        f"{filler}consumidor {'palavra ' * 20}",
        "sem termo " * 20,
    )

    assert head.score > body.score
    assert ementa.score > body.score
    assert other.score == 0


def test_matched_terms_lists_the_query_terms_found_with_accents_and_case_folded():
    first, second = _rank(
        'DECISÃO "dano moral" prazo',
        "Decisão sobre o DANO MORAL sofrido",
        "O prazo corre; decisão várias",
    )

    assert first.matched_terms == ("DECISÃO", "dano moral")
    assert second.matched_terms == ("DECISÃO", "prazo")


def test_terms_of_all_or_groups_count_once():
    terms = query_terms(parse_query("consumidor dano OR consumidor moral -ausente"))

    assert [t.text for t in terms] == ["consumidor", "dano", "moral"]


def test_the_best_item_of_a_page_scores_1_and_the_others_less():
    best, middle, worst = _rank(
        "dano moral",
        "dano moral dano moral",
        "dano moral " + "x " * 30,
        "dano " + "x " * 60,
    )

    assert best.score == 1.0
    assert 0 < worst.score < middle.score < 1.0


def test_a_page_where_every_item_holds_every_term_still_spreads_the_scores():
    short, long = _rank("consumidor", "consumidor " + "x " * 5, "consumidor " + "x " * 500)

    assert short.score == 1.0 and 0.1 < long.score < 1.0


def test_a_page_of_one_scores_1_and_a_page_with_no_match_scores_0():
    (only,) = _rank("consumidor", "o consumidor pediu")
    (nothing,) = _rank("consumidor", "outro assunto")

    assert only.score == 1.0 and nothing.score == 0.0


def test_an_empty_page_ranks_nothing():
    assert _rank("consumidor") == []


def test_a_page_of_25_long_texts_ranks_in_milliseconds():
    # It takes tens of milliseconds; the bound is loose on purpose so a slow runner cannot fail it.
    texts = [("O consumidor pediu dano moral e recurso especial. " * 1400)[:70_000]] * 25
    terms = query_terms(parse_query("consumidor dano recurso"))

    started = time.perf_counter()
    rank(terms, texts)

    assert time.perf_counter() - started < 3.0
