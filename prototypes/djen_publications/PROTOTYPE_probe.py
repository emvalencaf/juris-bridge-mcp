# ruff: noqa: E501, S310
"""PROTOTYPE, THROWAWAY (wayfinder ticket #62). Not production code; never merged.

Question: can the DJEN back the Publication search (court + period + free text, with
decisoes/acordaos selected on our side), and where does it break?

Usage:
  python3 -I PROTOTYPE_probe.py search <out.jsonl> <texto> <court,court> <start> <end>
      slice by court x day, page at 100/page, write one JSON line per item (raw, kept OUT of git)
  python3 -I PROTOTYPE_probe.py report <in.jsonl>
      classification histogram, text shape/length, CNJ numbers (aggregate only)
  python3 -I PROTOTYPE_probe.py sample <in.jsonl> <n>
      print n classified items (truncated) for hand-checking; do not commit the output

Read-only GETs, >= 1.5 s between requests, backs off on low x-ratelimit-remaining and on 429.
"""

import collections
import datetime as dt
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
UA = "Mozilla/5.0 (compatible; juris-bridge-mcp-prototype/0.1; +https://github.com/emvalencaf/juris-bridge-mcp)"
STATS = {
    "requests": 0,
    "latencies": [],
    "429": 0,
    "http_errors": collections.Counter(),
    "min_remaining": 99,
}


def get(params: dict) -> dict | None:
    url = BASE + "?" + urllib.parse.urlencode(params)
    for _ in range(3):
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60
            ) as r:
                body = json.load(r)
                rem = int(r.headers.get("x-ratelimit-remaining", 99))
        except urllib.error.HTTPError as e:
            STATS["requests"] += 1
            STATS["http_errors"][e.code] += 1
            if e.code == 429:
                STATS["429"] += 1
                time.sleep(61)
                continue
            return None
        STATS["requests"] += 1
        STATS["latencies"].append(time.monotonic() - t0)
        STATS["min_remaining"] = min(STATS["min_remaining"], rem)
        time.sleep(1.5 if rem > 5 else 20)
        return body
    return None


def days(start: str, end: str):
    d, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += dt.timedelta(days=1)


def search(out: str, texto: str, courts: list[str], start: str, end: str) -> None:
    with open(out, "w", encoding="utf-8") as f:
        for court in courts:
            for day in days(start, end):
                page, got, total = 1, 0, None
                while True:
                    body = get(
                        {
                            "siglaTribunal": court,
                            "texto": texto,
                            "dataDisponibilizacaoInicio": day,
                            "dataDisponibilizacaoFim": day,
                            "itensPorPagina": 100,
                            "pagina": page,
                        }
                    )
                    if body is None:
                        print(f"{court} {day} page {page}: failed", file=sys.stderr)
                        break
                    total = body["count"]
                    for it in body["items"]:
                        f.write(json.dumps(it, ensure_ascii=False) + "\n")
                    got += len(body["items"])
                    if len(body["items"]) < 100 or got >= PAGE_CAP:
                        break
                    page += 1
                print(f"{court} {day}: count={total} fetched={got} pages={page}", file=sys.stderr)
    lat = STATS["latencies"]
    print(
        f"requests={STATS['requests']} 429s={STATS['429']} errors={dict(STATS['http_errors'])} "
        f"min_remaining={STATS['min_remaining']} latency median={statistics.median(lat):.2f}s "
        f"max={max(lat):.2f}s",
        file=sys.stderr,
    )


PAGE_CAP = 600  # prototype politeness cap per court-day, not an API limit

# ---- classification: tipoComunicacao + tipoDocumento + text -> kind
TAG = re.compile(r"<[^>]+>")


def plain(texto: str) -> str:
    import html

    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", texto or ""))).strip()


def classify(it: dict) -> tuple[str, str]:
    """Return (kind, why). kind: acordao | decisao | despacho | intimacao | edital | pauta | other | ambiguous."""
    tc = (it.get("tipoComunicacao") or "").lower()
    td = (it.get("tipoDocumento") or "").lower()
    text = plain(it.get("texto")).lower()
    if "edital" in tc or "edital" in td or it.get("meio") == "E":
        return "edital", "tipo"
    if "pauta" in tc or "lista de distribui" in tc or "ata de sess" in tc:
        return "pauta", "tipoComunicacao"
    if "acórdão" in td or "acordao" in td:
        return "acordao", "tipoDocumento"
    if (
        "despacho/decis" in td.replace(" ", "")
        or "decisão" in td
        or "decisao" in td
        or "sentença" in td
    ):
        # DESPACHO / DECISAO is a combined label: only the text can tell which
        kind, why = classify_text(td, tc, text)
        return kind, "label combinado; " + why
    if "despacho" in td:
        return "despacho", "tipoDocumento"
    return classify_text(td, tc, text)


COMBINED = re.compile(r"despacho|decis|sentença")
SENTENCE = re.compile(
    r"\b(julgo (parcialmente )?(im)?procedentes?|julgo extint|julga-se|ante o exposto|isto posto|"
    r"dou provimento|nego provimento|condeno|homologo|decreto a|indefiro a (petição )?inicial|"
    r"dispositivo)\b"
)
NOTICE = re.compile(
    r"(ficam as partes e respectivos representantes cientificados|ato ordinat|fica(m)? intimad|"
    r"intimação da penhora|ciência às partes|certidão|prazo para)"
)
DESP = re.compile(
    r"^.{0,260}\b(vistos\.|cumpra-se|aguarde-se|int\.|intime-se|manifeste-se|diga|suspendo)"
)


def classify_text(td: str, tc: str, text: str) -> tuple[str, str]:
    """Generic labels ('Intimacao', 'Sentenca' with no marker, ...): only the text can say."""
    if re.search(r"\bementa\s*:", text) and not COMBINED.search(td):
        return "acordao", "texto tem EMENTA:"
    if SENTENCE.search(text):
        return "decisao", "texto: marcador de dispositivo/decisao"
    if NOTICE.search(text):
        return "notice", "texto: aviso/ato ordinatorio"
    if DESP.search(text):
        return "despacho", "texto: marcador de despacho"
    return "ambiguous", "nenhum marcador no texto"


def cnj_valid(n: str) -> bool:
    """CNJ Res. 65/2008 check digit: NNNNNNN DD AAAA J TR OOOO; valid when (N+AAAAJTROOOO+DD) mod 97 == 1."""
    if len(n) != 20 or not n.isdigit():
        return False
    return int(n[:7] + n[9:] + n[7:9]) % 97 == 1


def load(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def report(path: str) -> None:
    items = load(path)
    print(f"items: {len(items)}")
    by = collections.defaultdict(list)
    for it in items:
        by[it["siglaTribunal"]].append(it)
    for court, its in by.items():
        print(f"\n== {court}: {len(its)}")
        print(" tipoComunicacao:", dict(collections.Counter(i["tipoComunicacao"] for i in its)))
        print(
            " tipoDocumento:",
            dict(collections.Counter(i["tipoDocumento"] for i in its).most_common(8)),
        )
        kinds = collections.Counter(classify(i)[0] for i in its)
        print(" classified:", dict(kinds))
        html_n = sum(
            1 for i in its if re.search(r"<(p|table|div|br|span)\b", i["texto"] or "", re.I)
        )
        lens = sorted(len(plain(i["texto"])) for i in its)
        print(
            f" texto HTML: {html_n}/{len(its)}; plain length min/median/p90/max:",
            lens[0],
            lens[len(lens) // 2],
            lens[int(len(lens) * 0.9)],
            lens[-1],
        )
        print(
            " ementa inline:",
            sum(1 for i in its if re.search(r"\bementa\b", plain(i["texto"]), re.I)),
            "| cancelled/inactive:",
            sum(
                1 for i in its if not i.get("ativo", True) or i.get("status") not in (None, "P", "")
            ),
        )
    cnj = sorted({i["numero_processo"] for i in items if i.get("numero_processo")})
    print(f"\ndistinct CNJ numbers: {len(cnj)}; bad length: {sum(1 for c in cnj if len(c) != 20)}")
    print("distinct per item (duplicates of same process):", len(items) - len(cnj))
    print("CNJ check digit valid:", sum(cnj_valid(c) for c in cnj), "of", len(cnj))
    for court, its in by.items():
        cs = {i["numero_processo"] for i in its}
        print(
            f" {court}: {sum(cnj_valid(c) for c in cs)}/{len(cs)} valid; "
            f"masked form present: {sum(1 for i in its if i.get('numeroprocessocommascara'))}/{len(its)}"
        )


def sample(path: str, n: int) -> None:
    import random

    random.seed(7)
    items = load(path)
    for it in random.sample(items, min(n, len(items))):
        kind, why = classify(it)
        print(
            f"[{kind}] ({why}) {it['siglaTribunal']} tc={it['tipoComunicacao']!r} td={it['tipoDocumento']!r}\n"
            f"   {plain(it['texto'])[:260]}\n"
        )


def limits() -> None:
    """One-off probes of paging/cap/rate behaviour. Prints status + shape only, stores nothing."""

    def raw(params: dict, label: str):
        url = BASE + "?" + urllib.parse.urlencode(params)
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90
            ) as r:
                b = json.load(r)
                print(
                    f"{label}: 200 count={b['count']} items={len(b['items'])} {time.monotonic() - t0:.2f}s "
                    f"remaining={r.headers.get('x-ratelimit-remaining')}"
                )
        except urllib.error.HTTPError as e:
            print(f"{label}: HTTP {e.code} {time.monotonic() - t0:.2f}s")
        time.sleep(1.5)

    day = {
        "siglaTribunal": "TJSP",
        "texto": "prescrição",
        "dataDisponibilizacaoInicio": "2026-10-13",
        "dataDisponibilizacaoFim": "2026-10-13",
    }
    raw({**day, "itensPorPagina": 1000, "pagina": 1}, "TJSP 1 day, 1000/page p1")
    raw({**day, "itensPorPagina": 100, "pagina": 100}, "TJSP 1 day, 100/page p100")
    raw({**day, "itensPorPagina": 100, "pagina": 101}, "TJSP 1 day, 100/page p101")
    wk = {
        **day,
        "dataDisponibilizacaoInicio": "2026-10-12",
        "dataDisponibilizacaoFim": "2026-10-16",
    }
    raw({**wk, "itensPorPagina": 100, "pagina": 1}, "TJSP 5-day window")
    stj = {
        "siglaTribunal": "STJ",
        "texto": "prescrição",
        "dataDisponibilizacaoInicio": "2026-10-13",
        "dataDisponibilizacaoFim": "2026-10-13",
        "itensPorPagina": 100,
        "pagina": 1,
    }
    raw(stj, "STJ 1 day")
    raw(
        {**stj, "texto": "prescrição intercorrente"},
        "STJ 1 day 'prescrição intercorrente' (AND or phrase?)",
    )
    raw({**stj, "texto": '"prescrição intercorrente"'}, "STJ 1 day quoted phrase")
    raw({**stj, "texto": "zzqxkjw"}, "STJ 1 day nonsense term")
    raw({"siglaTribunal": "STF", "texto": "prescrição", "itensPorPagina": 5}, "STF")
    for i in range(12):
        raw({**stj, "itensPorPagina": 5, "pagina": 1 + i % 3}, f"burst {i}")
        time.sleep(-1.0) if False else None


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "search":
        search(sys.argv[2], sys.argv[3], sys.argv[4].split(","), sys.argv[5], sys.argv[6])
    elif cmd == "limits":
        limits()
    elif cmd == "report":
        report(sys.argv[2])
    elif cmd == "sample":
        sample(sys.argv[2], int(sys.argv[3]))
