"""Redaction of personal data from Source text."""

import pytest

from evals.redaction import CNPJ_PLACEHOLDER, CPF_PLACEHOLDER, NAME_PLACEHOLDER, redact


@pytest.mark.parametrize("cpf", ["123.456.789-09", "12345678909", "123.456.78909", "123456789-09"])
def test_cpf_is_replaced_in_every_written_form(cpf):
    assert redact(f"CPF {cpf} consta nos autos") == f"CPF {CPF_PLACEHOLDER} consta nos autos"


@pytest.mark.parametrize("cnpj", ["12.345.678/0001-95", "12345678000195", "12.345.678/000195"])
def test_cnpj_is_replaced_in_every_written_form(cnpj):
    assert redact(f"empresa {cnpj}, ré") == f"empresa {CNPJ_PLACEHOLDER}, ré"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Autor: João da Silva", f"Autor: {NAME_PLACEHOLDER}"),
        ("Réu: MARIA APARECIDA SOUZA, brasileira", f"Réu: {NAME_PLACEHOLDER}, brasileira"),
        ("requerente Pedro Alves requer", f"requerente {NAME_PLACEHOLDER} requer"),
        ("Advogado: Dr. Carlos Eduardo Lima", f"Advogado: Dr. {NAME_PLACEHOLDER}"),
        (
            "Intimem-se Ana Paula Ferreira e Rui Costa.",
            f"Intimem-se {NAME_PLACEHOLDER} e {NAME_PLACEHOLDER}.",
        ),
    ],
)
def test_names_after_roles_and_capitalised_runs_are_replaced(text, expected):
    assert redact(text) == expected


def test_institutional_phrases_are_not_taken_for_names():
    text = "O Superior Tribunal de Justiça e o Ministério Público Federal"

    assert redact(text) == text


def test_names_next_to_institutional_words_are_still_replaced():
    assert redact("Recurso Especial de João Silva") == f"Recurso Especial de {NAME_PLACEHOLDER}"


def test_cnj_court_alias_and_kind_sigla_are_left_alone():
    text = (
        "Proc. 0001234-56.2023.8.26.0100 (TJSP, TRF3) 00012345620238260100 "
        "Tema RG 1234, SUM 7, SV 13, RR, IRDR, IAC, OJ"
    )

    assert redact(text) == text


def test_role_followed_by_a_court_alias_keeps_the_alias():
    assert redact("Autor: TJSP") == "Autor: TJSP"


def test_structures_are_redacted_in_every_string_and_keys_are_kept():
    value = {"a": ["Réu: José Santos", 3, None], "n": {"cpf": "123.456.789-09"}}

    assert redact(value) == {
        "a": [f"Réu: {NAME_PLACEHOLDER}", 3, None],
        "n": {"cpf": CPF_PLACEHOLDER},
    }


def test_djen_parties_and_lawyers_are_redacted_by_their_keys():
    body = {
        "destinatarios": [{"comunicacao_id": 1, "nome": "FLAVIO LUIZ SILVA OLIVEIRA", "polo": "A"}],
        "destinatarioadvogados": [
            {"advogado": {"id": 3, "nome": "PRISCILLA JANTOLCIC COURI", "numero_oab": "168766"}}
        ],
        "numeroprocessocommascara": "1234567-76.2025.8.26.0100",
        "nomeOrgao": "1ª Vara Cível",
    }

    out = redact(body)

    assert out["destinatarios"][0]["nome"] == NAME_PLACEHOLDER
    assert out["destinatarioadvogados"][0]["advogado"]["nome"] == NAME_PLACEHOLDER
    assert out["destinatarioadvogados"][0]["advogado"]["numero_oab"] == "[OAB]"
    assert out["numeroprocessocommascara"] == "1234567-76.2025.8.26.0100"
    assert out["nomeOrgao"] == "1ª Vara Cível"


def test_a_nome_that_is_not_a_person_is_kept():
    classe = {"classe": {"codigo": 7, "nome": "procedimento comum"}}

    assert redact(classe) == classe


def test_lawyer_titles_registrations_and_advogado_markers_are_redacted():
    text = (
        "REQUERIDO: Fulano Silva ADVOGADO(A): JOSE AURELIO DE ARAUJO (DPE) - SP405006-N, "
        "Dr. FELIPE GONÇALVES PINTO, OAB/SP 123.456"
    )

    out = redact(text)

    for leaked in ("JOSE", "AURELIO", "FELIPE", "405006", "123.456"):
        assert leaked not in out


def test_precedent_ids_are_not_taken_for_a_registration():
    assert redact("RG1002 e TRF3 e stf-rg-1002") == "RG1002 e TRF3 e stf-rg-1002"


def test_a_role_glued_to_the_previous_word_is_still_found():
    out = redact(
        "Justiça ADVOGADO(A): JOSE AURELIO DE ARAUJO (DPE)ADVOGADO(A): ALMIR GONCALVES FILHO"
    )

    assert "JOSE" not in out
    assert "ALMIR" not in out


def test_a_name_before_a_registration_in_parentheses_is_redacted():
    assert redact("JOSÉ EDUARDO GOMES DA COSTA (SP123456)") == "[NOME] ([OAB])"


def test_a_name_before_cpf_or_oab_in_parentheses_is_redacted():
    assert redact("VALDIR ALVES NEVES (CPF: 123.456.789-09)") == "[NOME] (CPF: [CPF])"
    assert redact("MARCIO GONCALVES DELFINO (OAB 12345/SP)") == "[NOME] ([OAB])"


def test_a_name_before_id_cpf_or_a_role_in_parentheses_is_redacted():
    assert redact("CIERDI ALVES BRAGA (ID 123.456.789-09)") == "[NOME] (ID [CPF])"
    assert redact("SILVA DOS SANTOS (REQUERENTE)") == "[NOME] (REQUERENTE)"
