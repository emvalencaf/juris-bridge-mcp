import pytest

from juris_bridge_mcp.adapters.djen.publication_mapper import plain_text


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("DECISÃO\n  Vistos.\t Defiro.", "DECISÃO Vistos. Defiro."),
        ("<p>um</p><p>dois</p>", "um dois"),
        ("<td>Relator</td><td>Fulano</td>", "Relator Fulano"),
        ("<b>RECURSO</b>ESPECIAL", "RECURSOESPECIAL"),
        ("a &amp; b &lt;c&gt;", "a & b <c>"),
        ("antes<script>var x = 1;</script><style>p {}</style>depois", "antes depois"),
        ("", ""),
    ],
)
def test_strips_markup_and_collapses_whitespace(markup, expected):
    assert plain_text(markup) == expected
