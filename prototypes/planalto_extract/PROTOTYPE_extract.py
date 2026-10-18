"""PROTOTYPE, THROWAWAY (wayfinder ticket #14). Not production code; never merged.

Question: can get_legislation(article=...) be served by pattern-matching Planalto static HTML?

Usage: python PROTOTYPE_extract.py <dir-with-html> [norm-key article ...]
Fetch the HTML first with a browser-compatible UA, see README.md in this folder.
"""
import html
import re
import sys
from pathlib import Path

# ---- 1. HTML -> list of logical paragraphs (one <p> == one dispositive in Planalto markup)
P_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def paragraphs(doc: str) -> list[dict]:
    out = []
    for m in P_RE.finditer(doc):
        inner = m.group(1)
        text = html.unescape(TAG_RE.sub(" ", inner)).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        # strikethrough (<strike>/<s>) marks text removed by an amendment
        struck = bool(re.search(r"<(strike|s)\b", inner, re.I))
        # quoted article of ANOTHER norm inside an amending article: "Art. 337-E" links to ../Del2848.htm#art337e
        foreign = bool(re.match(r'\s*(?:<[^a/][^>]*>\s*)*<a\b[^>]*href="[^"#]+#art', inner, re.I))
        out.append({"text": text, "struck": struck, "foreign": foreign})
    return out


# ---- 2. classify
ART = re.compile(
    r"^Art\.?\s*(?P<num>\d+(?:\.\d+)*)\s*(?:º|°|o)?\s*(?P<suf>(?:-[A-Z]{1,2})?)\s*[.\-–]?\s*(?P<rest>.*)$"
)
PAR = re.compile(r"^(?:§\s*(?P<n>\d+)\s*(?:º|°|o)?|Parágrafo único)\s*[.\-–]?\s*(?P<rest>.*)$")
INC = re.compile(r"^(?P<n>[IVXLCDM]+)\s*[-–—]\s*(?P<rest>.*)$")
ALI = re.compile(r"^(?P<n>[a-z])\)\s*(?P<rest>.*)$")
STRUCT = re.compile(r"^(LIVRO|TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO|PARTE|DISPOSIÇÕES)\b", re.I)
REVOKED = re.compile(r"\((Revogad[oa]|Vetad[oa])[^)]*\)", re.I)
AMEND = re.compile(r"\((Redação dada|Incluíd[oa]|Vide|Regulamento|Vigência|Renumerad)[^)]*\)", re.I)


def art_key(m) -> str:
    return m.group("num").replace(".", "") + m.group("suf")


def slice_articles(paras: list[dict]) -> dict[str, dict]:
    """Return {article_key: {caput, items:[(kind,label,text)], revoked, annotations}}.

    Stops an article at the next Art. line or at a structural heading
    (CAPÍTULO...). Keeps only the FIRST occurrence of a key (amendment
    paragraphs quoting `Art. 5º` inside a 'Redação dada' block would otherwise
    clobber it)."""
    arts: dict[str, dict] = {}
    cur = None
    for p in paras:
        t = p["text"]
        if STRUCT.match(t) and len(t) < 120:
            cur = None
            continue
        m = ART.match(t)
        if m and not t.startswith(('"', "“")) and p.get("foreign"):
            cur = None  # quoted article of another norm: skip it and its sub-items
            continue
        if m and not t.startswith(('"', "“")):
            key = art_key(m)
            if key in arts:  # duplicate heading: keep first, unless the kept one is struck-through (superseded)
                if arts[key].get("struck") and not p["struck"] and not arts[key].get("range"):
                    del arts[key]  # re-insert below: the live redaction replaces the superseded one
                else:
                    cur = None
                    continue
            cur = {
                "key": key,
                "caput": m.group("rest").strip(),
                "items": [],
                "struck": p["struck"],
                "annotations": AMEND.findall(t),
                "revoked": bool(REVOKED.search(t)),
            }
            arts[key] = cur
            rng = re.match(r"^a\s*(?P<end>\d+(?:\.\d+)*)", cur["caput"])
            if rng and cur["revoked"]:
                lo, hi = int(m.group("num").replace(".", "")), int(rng.group("end").replace(".", ""))
                cur["range"] = (lo, hi)
                for n in range(lo + 1, hi + 1):
                    arts.setdefault(str(n), {**cur, "key": str(n), "caput": f"(revoked, see Art. {lo})", "items": []})
            continue
        if cur is None:
            continue
        kind = None
        for k, rx in (("paragraph", PAR), ("inciso", INC), ("alinea", ALI)):
            mm = rx.match(t)
            if mm:
                kind, label = k, (mm.groupdict().get("n") or "unico")
                break
        if kind is None:
            # continuation / stray text (annotation-only lines, 'Parágrafo único' variants, tables)
            kind, label = "other", ""
        cur["items"].append((kind, label, t))
        if REVOKED.search(t):
            cur["revoked"] = cur["revoked"] or kind == "other"
    return arts


# ---- 3. evaluation helpers (ground truth = known article counts of the norms)
GROUND_TRUTH_LAST = {  # last numbered article in the consolidated text, from the norm itself
    "cdc": 119,  # Lei 8.078/1990 (Art. 119 revoga disposicoes)
    "l14133": 194,  # Lei 14.133/2021
    "cc": 2046,  # Lei 10.406/2002
    "dec": None,
    "cf": 250,  # CF/88 permanent text (ADCT restarts at 1)
    "l8666": 126,  # Lei 8.666/1993
    "l9784": 70,  # Lei 9.784/1999 (first ground truth, 80, was my error)
}


def report(name: str, arts: dict[str, dict]):
    keys = list(arts)
    nums = [int(re.match(r"\d+", k).group()) for k in keys]
    base = sorted({n for n in nums})
    exp_last = GROUND_TRUTH_LAST.get(name)
    last = max(base) if base else 0
    missing = [n for n in range(1, (exp_last or last) + 1) if n not in set(base)]
    suffixed = [k for k in keys if not k.isdigit()]
    out_of_order = sum(1 for a, b in zip(nums, nums[1:]) if b < a)
    empty_caput = [k for k, a in arts.items() if not a["caput"] and not a["items"]]
    revoked = [k for k, a in arts.items() if a["revoked"]]
    items = sum(len(a["items"]) for a in arts.values())
    other = sum(1 for a in arts.values() for i in a["items"] if i[0] == "other")
    print(f"== {name}: {len(keys)} article keys ({len(suffixed)} with -A/-B suffix), last base={last}"
          f" (expected {exp_last}), missing base numbers={len(missing)}"
          f" {missing[:15]}{'...' if len(missing) > 15 else ''}")
    print(f"   out-of-order transitions={out_of_order}, revoked-flagged={len(revoked)}, "
          f"empty articles={len(empty_caput)} {empty_caput[:10]}, sub-items={items} ('other'={other})")
    return missing


def show(name: str, arts: dict, key: str):
    a = arts.get(key)
    print(f"\n--- {name} Art. {key} ---")
    if not a:
        print("NOT FOUND")
        return
    print(a["caput"][:300], "| revoked=", a["revoked"], "| struck=", a["struck"], "| annotations=", a["annotations"][:2])
    for kind, label, t in a["items"][:8]:
        print(f"  [{kind}:{label}] {t[:140]}")


if __name__ == "__main__":
    d = Path(sys.argv[1])
    cache = {}
    for f in sorted(d.glob("*.htm")):
        paras = paragraphs(decode(f.read_bytes()))
        cache[f.stem] = slice_articles(paras)
        report(f.stem, cache[f.stem])
    args = sys.argv[2:]
    while args:
        show(args[0], cache.get(args[0], {}), args[1])
        args = args[2:]
