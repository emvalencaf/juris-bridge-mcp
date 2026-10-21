import pytest

from juris_bridge_mcp.domain.publication_kind import PublicationKind as K
from juris_bridge_mcp.domain.publication_kind import classify_publication

# (tipoComunicacao, tipoDocumento, text, expected): a hand-labelled set shaped after the
# researched DJEN items; the texts are synthetic.
LABELLED = [
    # acórdão
    (
        "Intimação",
        "Intimação de acórdão",
        "EMENTA: RECURSO ESPECIAL. Provimento negado.",
        K.ACORDAO,
    ),
    ("Intimação", "EMENTA / ACORDÃO", "Relatório. Voto. Unânime.", K.ACORDAO),
    ("Intimação", "Intimação", "EMENTA: APELAÇÃO CÍVEL. Dano moral. Acórdão unânime.", K.ACORDAO),
    # sentença
    (
        "Intimação",
        "Sentença",
        "Vistos. Trata-se de ação de cobrança. Relatório e fundamentos.",
        K.SENTENCA,
    ),
    (
        "Intimação",
        "Intimação",
        "Vistos. Ante o exposto, JULGO PROCEDENTE o pedido. Custas.",
        K.SENTENCA,
    ),
    (
        "Intimação",
        "Intimação",
        "Isto posto, julgo extinto o processo, nos termos do art. 485.",
        K.SENTENCA,
    ),
    (
        "Intimação",
        "Intimação",
        "Julgo parcialmente procedentes os pedidos. Condeno o réu.",
        K.SENTENCA,
    ),
    ("Intimação", "Intimação", "Sentença. Homologo o acordo e julgo extinto o feito.", K.SENTENCA),
    # decisão monocrática
    (
        "Intimação",
        "DESPACHO / DECISÃO",
        "Trata-se de agravo. Ante o exposto, nego provimento ao recurso.",
        K.DECISAO_MONOCRATICA,
    ),
    (
        "Intimação",
        "DESPACHO / DECISÃO",
        "Relatório. Nego seguimento ao recurso especial.",
        K.DECISAO_MONOCRATICA,
    ),
    (
        "Intimação",
        "Intimação",
        "Relator. Dou provimento ao recurso, nos termos do art. 932.",
        K.DECISAO_MONOCRATICA,
    ),
    ("Intimação", "Decisão", "Não conheço do agravo. Publique-se.", K.DECISAO_MONOCRATICA),
    # decisão interlocutória
    (
        "Intimação",
        "Intimação",
        "DECISÃO Vistos. Defiro o pedido de tutela de urgência.",
        K.DECISAO_INTERLOCUTORIA,
    ),
    (
        "Intimação",
        "Intimação",
        "Indefiro a produção de prova pericial por desnecessária.",
        K.DECISAO_INTERLOCUTORIA,
    ),
    (
        "Intimação",
        "DESPACHO / DECISÃO",
        "Concedo a gratuidade da justiça ao autor.",
        K.DECISAO_INTERLOCUTORIA,
    ),
    # not a decision: dropped
    ("Edital", "Edital", "EDITAL DE CITAÇÃO com prazo de 20 dias.", K.NOT_A_DECISION),
    ("Lista de distribuição", "Intimação", "Relação de processos distribuídos.", K.NOT_A_DECISION),
    ("Intimação", "Despacho", "Cite-se o réu.", K.NOT_A_DECISION),
    ("Intimação", "Intimação", "DESPACHO Aguarde-se o prazo.", K.NOT_A_DECISION),
    (
        "Intimação",
        "Intimação",
        "Vistos. Intime-se a parte para manifestação em 15 dias.",
        K.NOT_A_DECISION,
    ),
    ("Intimação", "DESPACHO / DECISÃO", "Cumpra-se. Intimem-se.", K.NOT_A_DECISION),
    (
        "Intimação",
        "Intimação",
        "Ficam as partes e respectivos representantes cientificados de que o processo passará "
        "a tramitar no Eproc. Prescrição e Decadência.",
        K.NOT_A_DECISION,
    ),
    (
        "Intimação",
        "Intimação",
        "Ato ordinatório: intime-se o autor para ciência da certidão.",
        K.NOT_A_DECISION,
    ),
    # ambiguous: no marker, or a despacho and a ruling at once
    ("Intimação", "Intimação", "Processo em andamento. Nada mais.", K.AMBIGUOUS),
    ("Intimação", "DESPACHO / DECISÃO", "Petição juntada aos autos.", K.AMBIGUOUS),
    ("Intimação", "Intimação", "Vistos. Defiro a juntada e intime-se a parte.", K.AMBIGUOUS),
    ("Intimação", None, "", K.AMBIGUOUS),
]


@pytest.mark.parametrize(("communication", "label", "text", "expected"), LABELLED)
def test_classifies_the_labelled_set(communication, label, text, expected):
    assert (
        classify_publication(communication_type=communication, document_type=label, text=text)
        is expected
    )


def test_a_combined_label_does_not_make_a_quoted_ementa_an_acordao():
    text = "Contra o acórdão, que decidiu: EMENTA: APELAÇÃO. Recurso desprovido. Nego seguimento."

    kind = classify_publication(
        communication_type="Intimação", document_type="DESPACHO / DECISÃO", text=text
    )

    assert kind is K.DECISAO_MONOCRATICA


def test_the_dispositive_is_read_at_the_end_not_in_a_quoted_sentence():
    text = "A sentença disse: julgo procedente o pedido. " + "x " * 3000 + "Cumpra-se."

    kind = classify_publication(
        communication_type="Intimação", document_type="DESPACHO / DECISÃO", text=text
    )

    assert kind is not K.SENTENCA


def test_accents_and_case_do_not_matter():
    kind = classify_publication(
        communication_type="INTIMAÇÃO", document_type="SENTENÇA", text="RELATÓRIO. FUNDAMENTOS."
    )

    assert kind is K.SENTENCA
