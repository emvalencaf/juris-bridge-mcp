"""Redaction of personal data from Source text: patterns, NER names and their numbering."""

import pytest

from evals.redaction import (
    CNPJ_PLACEHOLDER,
    CPF_PLACEHOLDER,
    OAB_PLACEHOLDER,
    Redactor,
    redact,
)


def person(n: int) -> str:
    return f"[PESSOA {n}]"


@pytest.mark.parametrize("cpf", ["123.456.789-09", "12345678909", "123.456.78909", "123456789-09"])
def test_cpf_is_fully_masked_in_every_written_form(cpf):
    out = redact(f"CPF {cpf} consta nos autos")

    assert out == f"CPF {CPF_PLACEHOLDER} consta nos autos"
    assert "789" not in out


@pytest.mark.parametrize("cnpj", ["12.345.678/0001-95", "12345678000195", "12.345.678/000195"])
def test_cnpj_is_replaced_in_every_written_form(cnpj):
    assert redact(f"empresa {cnpj}, ré") == f"empresa {CNPJ_PLACEHOLDER}, ré"


@pytest.mark.parametrize("cnpj", ["06.871.830/0002-\n 51", "39.911.488/0001&#x2011;44"])
def test_cnpj_with_a_wrapped_or_entity_hyphen_is_replaced(cnpj):
    assert redact(f"CNPJ {cnpj}, ré") == f"CNPJ {CNPJ_PLACEHOLDER}, ré"


def test_cnj_court_alias_and_kind_sigla_are_left_alone():
    text = (
        "Proc. 0001234-56.2023.8.26.0100 (TJSP, TRF3) 00012345620238260100 "
        "Tema RG 1234, SUM 7, SV 13, RR, IRDR, IAC, OJ"
    )

    assert redact(text) == text


def test_ner_finds_people_without_a_role():
    out = redact("Intimem-se Ana Paula Ferreira e Rui Costa.")

    assert out == f"Intimem-se {person(1)} e {person(2)}."


def test_the_same_person_gets_the_same_number_whatever_the_writing():
    r = Redactor()

    out = [
        r.redact("Autor: João da Silva"),
        r.redact("Réu: Maria Aparecida Souza"),
        r.redact("Intimado JOAO SILVA para"),
        r.redact("o autor João  da   Silva requereu"),
    ]

    assert out[0] == f"Autor: {person(1)}"
    assert out[1] == f"Réu: {person(2)}"
    assert out[2] == f"Intimado {person(1)} para"
    assert out[3] == f"o autor {person(1)} requereu"


def test_a_longer_form_of_a_name_is_the_same_person_but_a_clashing_one_is_not():
    r = Redactor()

    first = r.redact("Autor: João Silva")
    longer = r.redact("Autor: João Carlos Silva")
    other = r.redact("Autor: João Pereira")

    assert (first, longer, other) == (
        f"Autor: {person(1)}",
        f"Autor: {person(1)}",
        f"Autor: {person(2)}",
    )


def test_two_people_sharing_only_a_surname_are_different():
    r = Redactor()

    assert r.redact("Pedro Alves e Carlos Alves") == f"{person(1)} e {person(2)}"


def test_a_fresh_redactor_starts_again_from_one():
    Redactor().redact("Autor: João da Silva")

    assert Redactor().redact("Autor: Maria Souza") == f"Autor: {person(1)}"


@pytest.mark.parametrize(
    "text",
    [
        "O Código de Defesa do Consumidor prevê a inversão",
        "Mérito Julgado pelo Superior Tribunal de Justiça",
        "O Superior Tribunal de Justiça e o Ministério Público Federal",
        "Recurso Especial no Tribunal de Justiça de São Paulo, 1ª Vara Cível",
        "Súmula 7 do STJ e Tema 1234",
    ],
)
def test_legal_terms_and_institutions_are_not_taken_for_people(text):
    assert redact(text) == text


def test_a_lone_word_the_model_tags_as_a_person_is_kept():
    text = {"situacao": "Admitido", "outra": "Vigente"}

    assert redact(text) == text


def test_a_name_the_model_cuts_at_a_connector_is_one_person():
    out = redact("Rel. Ministro Paulo de Tarso Sanseverino votou")

    assert out == f"Rel. Ministro {person(1)} votou"


@pytest.mark.parametrize(
    "text",
    [
        "nos termos do artigo 487, inciso I, do CPC",
        "Sentença Homologatória, Juiz Titular da Vara",
        "art. 105, III, a, da Constituição",
    ],
)
def test_legal_citations_and_court_posts_are_not_people(text):
    assert redact(text) == text


def test_html_entities_are_read_as_text_and_names_in_them_are_replaced_whole():
    out = redact(
        "<td>JOS&Eacute; DA SILVA</td> em Embargos de Declara&ccedil;&atilde;o C&iacute;vel"
    )

    assert out == f"<td>{person(1)}</td> em Embargos de Declara&ccedil;&atilde;o C&iacute;vel"


def test_shouted_legal_headings_are_not_people():
    text = "QUEST&Atilde;O EM DISCUSS&Atilde;O: realização de PERÍCIA MÉDICA na parte autora"

    assert redact(text) == text


def test_names_next_to_institutional_words_are_still_replaced():
    out = redact("Apelação de João Silva em face do Estado")

    assert out == f"Apelação de {person(1)} em face do Estado"


def test_upper_case_names_are_found():
    out = redact("Intimado FLAVIO LUIZ SILVA OLIVEIRA do despacho")

    assert out == f"Intimado {person(1)} do despacho"


def test_role_prefixed_names_the_model_misses_are_caught_by_the_fallback():
    out = redact("REQUERIDO: FULANO BELTRANO CICRANO ADVOGADO(A): JOSE AURELIO DE ARAUJO (DPE)")

    for leaked in ("FULANO", "CICRANO", "JOSE", "AURELIO", "ARAUJO"):
        assert leaked not in out
    assert "(DPE)" in out


def test_role_followed_by_a_court_alias_keeps_the_alias():
    assert redact("Autor: TJSP") == "Autor: TJSP"


def test_titles_stay_and_the_name_goes():
    out = redact("Dr. FELIPE GONÇALVES PINTO e Dra. Marta Lopes")

    assert out == f"Dr. {person(1)} e Dra. {person(2)}"


def test_org_and_loc_are_untouched():
    text = "Banco do Brasil em São Paulo, Praça Tiradentes"

    assert redact(text) == text


def test_structures_are_redacted_in_every_string_and_keys_are_kept():
    value = {"a": ["Réu: José Santos", 3, None], "n": {"cpf": "123.456.789-09"}}

    assert redact(value) == {
        "a": [f"Réu: {person(1)}", 3, None],
        "n": {"cpf": CPF_PLACEHOLDER},
    }


def test_djen_parties_and_lawyers_share_the_numbering_with_the_text():
    r = Redactor()
    body = {
        "texto": "Intimado Flavio Luiz Silva Oliveira.",
        "destinatarios": [{"comunicacao_id": 1, "nome": "FLAVIO LUIZ SILVA OLIVEIRA", "polo": "A"}],
        "destinatarioadvogados": [
            {"advogado": {"id": 3, "nome": "PRISCILLA JANTOLCIC COURI", "numero_oab": "168766"}}
        ],
        "numeroprocessocommascara": "1234567-76.2025.8.26.0100",
        "nomeOrgao": "1ª Vara Cível",
    }

    out = r.redact(body)

    assert out["texto"] == f"Intimado {person(1)}."
    assert out["destinatarios"][0]["nome"] == person(1)
    assert out["destinatarioadvogados"][0]["advogado"]["nome"] == person(2)
    assert out["destinatarioadvogados"][0]["advogado"]["numero_oab"] == OAB_PLACEHOLDER
    assert out["numeroprocessocommascara"] == "1234567-76.2025.8.26.0100"
    assert out["nomeOrgao"] == "1ª Vara Cível"


def test_a_nome_that_is_not_a_person_is_kept():
    classe = {"classe": {"codigo": 7, "nome": "procedimento comum"}}

    assert redact(classe) == classe


def test_lawyer_registrations_are_redacted_and_names_before_them_too():
    out = redact("JOSÉ EDUARDO GOMES DA COSTA (SP123456) e MARCIO GONCALVES DELFINO (OAB 12345/SP)")

    assert out == f"{person(1)} ({OAB_PLACEHOLDER}) e {person(2)} ({OAB_PLACEHOLDER})"


def test_a_name_before_cpf_in_parentheses_is_redacted_and_the_cpf_masked():
    assert redact("VALDIR ALVES NEVES (CPF: 123.456.789-09)") == f"{person(1)} (CPF: [CPF])"


def test_precedent_ids_are_not_taken_for_a_registration():
    assert redact("RG1002 e TRF3 e stf-rg-1002") == "RG1002 e TRF3 e stf-rg-1002"


def test_a_legacy_name_placeholder_is_left_alone_and_not_numbered():
    r = Redactor()
    body = {
        "destinatarios": [{"nome": "[NOME]", "polo": "A"}],
        "texto": "Autor: [NOME] e Rui Costa",
    }

    out = r.redact(body)

    assert out["destinatarios"][0]["nome"] == "[NOME]"
    assert out["texto"] == f"Autor: [NOME] e {person(1)}"


def test_a_role_glued_to_the_previous_word_is_still_found():
    out = redact(
        "Justiça ADVOGADO(A): JOSE AURELIO DE ARAUJO (DPE)ADVOGADO(A): ALMIR GONCALVES FILHO"
    )

    assert "JOSE" not in out
    assert "ALMIR" not in out
