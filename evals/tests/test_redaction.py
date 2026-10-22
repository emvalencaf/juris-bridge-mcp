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
