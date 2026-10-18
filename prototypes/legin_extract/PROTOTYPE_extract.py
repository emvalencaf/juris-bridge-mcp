"""PROTOTYPE, THROWAWAY (wayfinder ticket #16). Not production code; never merged.

Question: can get_legislation(article=...) be served by pattern-matching Camara Legin
"Texto Atualizado" HTML (and DOCX when the HTML 504s), as it was on Planalto (#14)?

Reuses the Planalto prototype (PROTOTYPE_planalto_base.py, same paragraph model) and adds
what Legin needs: `Arts. N a M.` revoked-range headings, Legin remark shapes, DOCX
fallback, body validation, and flags from the "Dados da Norma" metadata page.

Usage: python3 PROTOTYPE_extract.py <dir with <key>.htm|.docx and <key>_meta.html> [key article ...]
"""
import html
import re
import sys
import zipfile
from pathlib import Path

import PROTOTYPE_planalto_base as base

# ---- Legin-specific patterns -------------------------------------------------------------
ART_RANGE = re.compile(r"^Arts?\.?\s*(?P<lo>\d+(?:\.\d+)*)\s*(?:º|°)?\s*a\s*(?P<hi>\d+(?:\.\d+)*)\s*(?:º|°)?\s*\.?\s*(?P<rest>.*)$")
# Legin wording varies: "(Revogado pela ...)", "(“Caput” do artigo revogado pela ...)",
# "(Artigo acrescido pela ... e revogado pela ...)"
REVOKED = re.compile(r"\([^)]*\b(?:revogad[oa]s?|vetad[oa]s?)\b[^)]*\)", re.I)
# Legin remarks: "(Inciso com redação dada pela ...)", "(Inciso acrescido pela ...)", "(Vide Emenda ...)"
REMARK = re.compile(r"\(((?:[A-Za-zçãéí ]*?)(?:redação dada|acrescid[oa]|incluíd[oa]|renumerad[oa]|Vide|Regulamento|Vigência)[^)]*)\)", re.I)


def valid_body(raw: bytes) -> bool:
    """Legin answers HTTP 200 with a 160-byte '504 Gateway Time-out' body: check the body, not the status."""
    return len(raw) > 5000 and b"504 Gateway" not in raw[:400] and b"<p" in raw


def docx_paragraphs(path: Path) -> list[dict]:
    """Fallback when the HTML is stuck on 504: one <w:p> == one logical paragraph (stdlib only)."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for m in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", m.group(0)))
        text = re.sub(r"\s+", " ", html.unescape(text).replace("\xa0", " ")).strip()
        if text:
            out.append({"text": text, "struck": "<w:strike" in m.group(0), "foreign": False})
    return out


JUMP = 25  # DOCX has no <a href> to flag quoted articles of other norms; use numeric continuity instead


def slice_articles(paras: list[dict]) -> dict[str, dict]:
    """Planalto slicer + `Arts. N a M.` ranges + broader remark detection + numeric-continuity guard.
    Keeps first occurrence."""
    arts: dict[str, dict] = {}
    cur = None
    top = 0  # highest accepted base article number so far
    for p in paras:
        t = p["text"]
        if base.STRUCT.match(t) and len(t) < 120:
            cur = None
            continue
        mr = ART_RANGE.match(t)
        if mr and REVOKED.search(mr.group("rest")):
            lo, hi = int(mr.group("lo").replace(".", "")), int(mr.group("hi").replace(".", ""))
            top = max(top, hi)
            for n in range(lo, hi + 1):
                arts.setdefault(str(n), {"key": str(n), "caput": f"(revoked, range Arts. {lo} a {hi})", "items": [],
                                         "struck": False, "annotations": [], "revoked": True, "range": (lo, hi)})
            cur = None
            continue
        m = base.ART.match(t)
        if m and not t.startswith(('"', "“")):
            key = base.art_key(m)
            num = int(m.group("num").replace(".", ""))
            if key in arts or num < top - 1 or num > top + JUMP:  # duplicate / regression / jump: quoted or annex
                cur = None
                continue
            top = max(top, num)
            cur = {"key": key, "caput": m.group("rest").strip(), "items": [], "struck": p["struck"],
                   "annotations": REMARK.findall(t), "revoked": bool(REVOKED.search(t))}
            arts[key] = cur
            continue
        if cur is None:
            continue
        kind, label = "other", ""
        for k, rx in (("paragraph", base.PAR), ("inciso", base.INC), ("alinea", base.ALI)):
            mm = rx.match(t)
            if mm:
                kind, label = k, (mm.groupdict().get("n") or "unico")
                break
        cur["items"].append((kind, label, t))
        cur["annotations"] += REMARK.findall(t)
        if REVOKED.search(t) and kind == "other":
            cur["revoked"] = True
    return arts


# ---- flags from the Dados da Norma page ---------------------------------------------------
def metadata_flags(doc: str) -> dict:
    """Parse the Dados da Norma list: <li><a>Norm nº N de D (Poder) - (Relation). Art. X, ... ; Art. Y .</a></li>.
    Returns {article_key: [(norm, relation)]}; norms without article refs map nowhere (whole-norm relations)."""
    out: dict[str, list] = {}
    for li in re.finditer(r"<li>\s*<a [^>]*>(.*?)</a>", doc, re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", li.group(1)))).strip()
        m = re.match(r"(?P<norm>.*?nº \d+ de .*?)\s*-\s*\((?P<rel>[^)]+)\)\.?\s*(?P<refs>.*)$", t)
        if not m:
            continue
        for a in re.finditer(r"Art\.?\s*(\d+)º?(?:-([A-Z]))?", m.group("refs")):
            out.setdefault(a.group(1) + (a.group(2) or ""), []).append((m.group("norm"), m.group("rel")))
    return out


GROUND_TRUTH_LAST = {"cdc": 119, "l14133": 194, "cc": 2046, "cf": 250, "l8666": 126, "l9784": 70}


def load(d: Path, key: str):
    htm = d / f"{key}.htm"
    if htm.exists() and valid_body(htm.read_bytes()):
        return "html", base.paragraphs(base.decode(htm.read_bytes()))
    dx = d / f"{key}.docx"
    if dx.exists():
        return "docx", docx_paragraphs(dx)
    return None, []


def report(name, src, arts):
    nums = [int(re.match(r"\d+", k).group()) for k in arts]
    exp = GROUND_TRUTH_LAST.get(name)
    base_set = set(nums)
    missing = [n for n in range(1, (exp or max(base_set, default=0)) + 1) if n not in base_set]
    sub = sum(len(a["items"]) for a in arts.values())
    print(f"== {name} [{src}]: {len(arts)} keys ({sum(1 for k in arts if not k.isdigit())} -A/-B), "
          f"last={max(base_set, default=0)} expected={exp}, missing={len(missing)} {missing[:12]}")
    print(f"   revoked-flagged={sum(1 for a in arts.values() if a['revoked'])}, "
          f"with-remarks={sum(1 for a in arts.values() if a['annotations'])}, struck={sum(1 for a in arts.values() if a['struck'])}, "
          f"empty={sum(1 for a in arts.values() if not a['caput'] and not a['items'])}, sub-items={sub} "
          f"('other'={sum(1 for a in arts.values() for i in a['items'] if i[0]=='other')})")


if __name__ == "__main__":
    d = Path(sys.argv[1])
    cache = {}
    for meta in sorted(d.glob("*_meta.html")):
        key = meta.name[: -len("_meta.html")]
        src, paras = load(d, key)
        if not paras:
            print(f"== {key}: NO CONSOLIDATED TEXT (html 504/absent, no docx)")
            continue
        cache[key] = slice_articles(paras)
        report(key, src, cache[key])
        fl = metadata_flags(meta.read_text("utf-8", "replace"))
        print(f"   metadata: {len(fl)} article keys with norms listed; "
              f"Art. 6 -> {[r for _, r in fl.get('6', [])][:4]}")
        cache[key + "#meta"] = fl
    args = sys.argv[2:]
    while args:
        a = cache.get(args[0], {}).get(args[1])
        print(f"\n--- {args[0]} Art. {args[1]} ---")
        if a:
            print(a["caput"][:200], "| revoked=", a["revoked"], "| remarks=", a["annotations"][:2])
            for kind, label, t in a["items"][:6]:
                print(f"  [{kind}:{label}] {t[:110]}")
        else:
            print("NOT FOUND")
        args = args[2:]
