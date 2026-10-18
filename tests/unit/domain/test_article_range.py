from juris_bridge_mcp.domain.legislation_text import MAX_RANGE_ARTICLES, article_range


def test_a_range_covers_every_number_between_its_ends():
    assert article_range("Arts. 757 a 760. (Revogados)") == ("757", "758", "759", "760")
    assert article_range("Arts. 1.620 a 1.622. (Revogados)") == ("1620", "1621", "1622")


def test_an_e_names_just_the_two_articles():
    assert article_range("Arts. 4º e 6º (Revogados)") == ("4", "6")


def test_a_backwards_or_huge_range_is_not_a_stub():
    assert article_range("Arts. 9 a 3 (Revogados)") is None
    assert article_range(f"Arts. 1 a {MAX_RANGE_ARTICLES + 1} (Revogados)") is None


def test_any_other_line_is_not_a_stub():
    assert article_range("Art. 757. (Revogado)") is None
    assert article_range("Os arts. 757 a 777 foram revogados") is None
