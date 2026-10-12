"""Primary legal texts at article level: parse, validate, store and load.

A norm (law, decree, reglamento, resolution) lives in laws/<norm-id>/:

  norm.json        metadata of the stored version (source, hash, counts)
  articles.jsonl   one unit (article, transitorio) per line, verbatim text
  text.md          human-readable rendering

laws/registry.json lists the norms the engine should hold. Parsing works on
plain text lines, so SCIJ HTML, other HTML and PDFs (via pdftotext) share one
splitter. Standard library only, except pdftotext for PDFs.
"""

import hashlib
import html
import json
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from .corpus import REPO_ROOT

LAWS_DIR = REPO_ROOT / "laws"
AREAS = {"laboral", "ccss", "tributario", "contable", "mercantil", "general"}
RANKS = [
    "constitucion",
    "tratado",
    "ley",
    "decreto",
    "resolucion-general",
    "jurisprudencia-vinculante",
    "jurisprudencia",
    "dictamen-pgr",
    "oficio",
    "secondary",
]
SCIJ_TEXT_URL = (
    "https://pgrweb.go.cr/scij/Busqueda/Normativa/Normas/nrm_texto_completo.aspx"
    "?param1=NRTC&nValor1=1&nValor2={nrm}&nValor3={version}&strTipM=TC"
)
USER_AGENT = "cr-tax-kb ingest (Fact3; one request per named norm)"


@dataclass
class Unit:
    id: str
    norm_id: str
    norm_title: str
    kind: str  # articulo, transitorio
    number: str
    heading: str = ""
    path: list = field(default_factory=list)
    text: str = ""
    notes: list = field(default_factory=list)
    status: str = "vigente"
    area: str = ""
    rank: str = ""
    version_date: str = ""
    source_url: str = ""
    retrieved_at: str = ""
    source_sha256: str = ""
    text_sha256: str = ""


# ---------------------------------------------------------------- text input


class _TextExtractor(HTMLParser):
    """HTML to text lines: block tags end a line, scripts and styles dropped."""

    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_lines(raw):
    p = _TextExtractor()
    p.feed(raw)
    return clean_lines("".join(p.parts))


def pdf_to_lines(path):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is needed for PDFs (poppler-utils)")
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True, check=True)
    return clean_lines(out.stdout.decode("utf-8"))


def clean_lines(text):
    text = unicodedata.normalize("NFC", html.unescape(text)).replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines())
    return [ln for ln in lines if ln]


def read_source(path):
    """Return (lines, raw_bytes) for a saved HTML, PDF or text file."""
    path = Path(path)
    raw = path.read_bytes()
    if raw[:4] == b"%PDF":
        return pdf_to_lines(path), raw
    text = decode(raw)
    if re.search(r"<(html|body|p|div)\b", text[:5000], re.I):
        return html_to_lines(text), raw
    return clean_lines(text), raw


def decode(raw):
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------- parsing

SUFFIX = r"(bis|ter|qu[aá]ter|quinquies|sexies|septies|octies)?"
# A unit heading needs a separator after the number ("ARTÍCULO 1.-",
# "Artículo 10 bis.-", "Artículo 2°-") so in-text references that happen to
# start a line ("Artículo 5 de esta ley...") are not taken as new units.
ARTICLE = re.compile(r"^(?:ART[IÍ]CULO|Art[ií]culo|Art\.)\s+(\d+)\s*[°º]?\s*" + SUFFIX + r"\s*[°º]?\s*[.:\-–]+\s*(.*)$", re.I)
TRANSITORIO = re.compile(r"^TRANSITORIO\s+([IVXLCDM]+|\d+|[ÚU]NICO)\s*[°º]?\s*[.:\-–]+\s*(.*)$", re.I)
STRUCTURE = re.compile(r"^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|SUBSECCI[OÓ]N)\b", re.I)
NOTE = re.compile(
    r"^\((?:As[ií]|Reformad|Adicionad|Derogad|Anulad|Interpretad|Corrid|Modificad|Ver|Nota|Por resoluci|Mediante|La Sala|"
    r"Este art[ií]culo|El presente)",
    re.I,
)
NOISE = re.compile(r"^(Ficha (del )?art[ií]culo|Volver arriba|Imprimir|\[?Subir\]?)$", re.I)
LEVEL = {"libro": 0, "titulo": 1, "capitulo": 2, "seccion": 3, "subseccion": 4}
VERSION_DATE = re.compile(r"[Vv]ersi[oó]n (?:de la norma )?\d+ de \d+ del (\d{1,2})/(\d{1,2})/(\d{4})")


def _fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _number(raw, suffix):
    n = raw.lstrip("0") or "0"
    if suffix:
        n += " " + _fold(suffix.strip())
    return n


def find_version_date(lines):
    for ln in lines[:200]:
        m = VERSION_DATE.search(ln)
        if m:
            d, mth, y = m.groups()
            return f"{y}-{int(mth):02d}-{int(d):02d}"
    return ""


def parse_units(lines, norm_id, start_pattern=None):
    """Split text lines into units. Lines before the first unit (title, preamble)
    are skipped; a structure heading (Título, Capítulo...) and the line right
    after it (its name) become the path of the following units."""
    if start_pattern:
        rx = re.compile(start_pattern, re.I)
        for i, ln in enumerate(lines):
            if rx.search(ln):
                lines = lines[i:]
                break
    units, path, cur, pending_name = [], [], None, None
    for ln in lines:
        if NOISE.match(ln):
            continue
        m_art, m_tr = ARTICLE.match(ln), TRANSITORIO.match(ln)
        if m_art or m_tr:
            if m_art:
                kind, num, rest = "articulo", _number(m_art.group(1), m_art.group(2)), m_art.group(3)
            else:
                kind, num, rest = "transitorio", _fold(m_tr.group(1)).upper(), m_tr.group(2)
            heading, body = _split_heading(rest)
            cur = {"kind": kind, "number": num, "heading": heading, "path": list(path), "lines": [], "notes": []}
            if body:
                cur["lines"].append(body)
            units.append(cur)
            pending_name = None
            continue
        if STRUCTURE.match(ln) and len(ln) < 160:
            level = LEVEL.get(_fold(ln.split()[0]), 4)
            path = [p for p in path if p[0] < level] + [(level, ln)]
            pending_name = level
            continue
        if pending_name is not None and len(ln) < 160 and not NOTE.match(ln):
            # Name of the Título/Capítulo printed on its own line.
            path[-1] = (path[-1][0], f"{path[-1][1]} {ln}")
            pending_name = None
            continue
        pending_name = None
        if cur is None:
            continue
        if NOTE.match(ln):
            cur["notes"].append(ln)
        else:
            cur["lines"].append(ln)
    out = []
    for u in units:
        u["path"] = [p[1] for p in u["path"]]
        text = "\n".join(u.pop("lines")).strip()
        u["text"] = text
        u["status"] = "derogado" if _is_repealed(text, u["notes"]) else "vigente"
        out.append(u)
    return out


def _split_heading(rest):
    """Return (epígrafe guess, verbatim text). The text always keeps the whole
    line, so a wrong guess never alters the article; the guess is a short
    leading phrase ending in a period, e.g. 'Ámbito de aplicación.'"""
    rest = rest.strip().lstrip("-–. ").strip()
    m = re.match(r"^([A-ZÁÉÍÓÚÑ][^.]{2,90})\.\s*[-–]?\s*\S", rest)
    if m and len(m.group(1).split()) <= 6:
        return m.group(1).strip(), rest
    return "", rest


def _is_repealed(text, notes):
    t = _fold(text).strip(" .()")
    if t in ("", "derogado", "derogada") and any("derog" in _fold(n) for n in notes):
        return True
    return t.startswith("derogado") and len(t) < 200


def validate(units, expected_title=None, lines=None):
    """Return a list of problems. Empty means the parse looks sound."""
    problems = []
    if not units:
        return ["no units found"]
    if expected_title and lines is not None:
        head = _fold(" ".join(lines[:80]))
        if _fold(expected_title) not in head:
            problems.append(f"title '{expected_title}' not found near the top of the source")
    seen, last = set(), 0
    for u in units:
        key = (u["kind"], u["number"])
        if key in seen:
            problems.append(f"duplicate {u['kind']} {u['number']}")
        seen.add(key)
        if u["kind"] == "articulo" and u["number"].isdigit():
            n = int(u["number"])
            if n > last + 1:
                missing = f"{last + 1}" if n == last + 2 else f"{last + 1} to {n - 1}"
                problems.append(f"gap: article {missing} missing")
            last = max(last, n)
        if not u["text"] and u["status"] != "derogado":
            problems.append(f"{u['kind']} {u['number']} has no text")
    return problems


def unit_id(norm_id, kind, number):
    if kind == "articulo":
        return f"{norm_id}:art-{number.replace(' ', '-').lower()}"
    return f"{norm_id}:trans-{number.upper()}"


def build_units(parsed, norm, source):
    """Attach norm metadata and hashes. Duplicate numbers (e.g. transitorios
    of several reforming laws) get a -2, -3 suffix so ids stay unique."""
    out, counts = [], {}
    for p in parsed:
        uid = unit_id(norm["id"], p["kind"], p["number"])
        counts[uid] = counts.get(uid, 0) + 1
        if counts[uid] > 1:
            uid = f"{uid}-{counts[uid]}"
        out.append(
            Unit(
                id=uid,
                norm_id=norm["id"],
                norm_title=norm["title"],
                kind=p["kind"],
                number=p["number"],
                heading=p["heading"],
                path=p["path"],
                text=p["text"],
                notes=p["notes"],
                status=p["status"],
                area=norm.get("area", ""),
                rank=norm.get("rank", ""),
                version_date=source.get("version_date", ""),
                source_url=source.get("url", ""),
                retrieved_at=source.get("retrieved_at", ""),
                source_sha256=source.get("sha256", ""),
                text_sha256=hashlib.sha256(p["text"].encode("utf-8")).hexdigest(),
            )
        )
    return out


# ------------------------------------------------------------------- storage


def load_registry(root=None):
    path = Path(root or LAWS_DIR) / "registry.json"
    return json.loads(path.read_text(encoding="utf-8"))["norms"]


def registry_entry(norm_id, root=None):
    for n in load_registry(root):
        if n["id"] == norm_id:
            return n
    raise KeyError(f"{norm_id} is not in laws/registry.json")


def write_norm(norm, units, source, problems, root=None):
    d = Path(root or LAWS_DIR) / norm["id"]
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        **{k: norm[k] for k in ("id", "title", "number", "type", "area", "rank") if k in norm},
        "version_date": source.get("version_date", ""),
        "source_url": source.get("url", ""),
        "retrieved_at": source.get("retrieved_at", ""),
        "source_sha256": source.get("sha256", ""),
        "units": len(units),
        "articles": sum(u.kind == "articulo" for u in units),
        "transitorios": sum(u.kind == "transitorio" for u in units),
        "derogados": sum(u.status == "derogado" for u in units),
        "warnings": problems,
    }
    (d / "norm.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(d / "articles.jsonl", "w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(asdict(u), ensure_ascii=False) + "\n")
    (d / "text.md").write_text(render_markdown(meta, units), encoding="utf-8")
    return d


def render_markdown(meta, units):
    lines = [
        f"# {meta['title']}",
        "",
        f"Version of {meta['version_date'] or 'unknown date'}, retrieved {meta['retrieved_at']} from {meta['source_url']}.",
        "Generated by `cr_tax_kb.cli ingest`; do not edit by hand.",
        "",
    ]
    last_path = None
    for u in units:
        if u.path != last_path:
            for p in u.path:
                lines += [f"## {p}", ""]
            last_path = u.path
        label = "Artículo" if u.kind == "articulo" else "Transitorio"
        title = f"### {label} {u.number}" + (f". {u.heading}" if u.heading else "")
        lines += [title, f"<!-- cite: {u.id} -->", "", u.text or "(sin texto)", ""]
        lines += [f"> {n}" for n in u.notes] + ([""] if u.notes else [])
    return "\n".join(lines)


def load_units(root=None):
    root = Path(root or LAWS_DIR)
    units = []
    for path in sorted(root.glob("*/articles.jsonl")):
        with open(path, encoding="utf-8") as f:
            units += [Unit(**json.loads(ln)) for ln in f if ln.strip()]
    return units


def load_norms(root=None):
    root = Path(root or LAWS_DIR)
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*/norm.json"))]


# ------------------------------------------------------------------- ingest


def ingest(norm_id, file=None, url=None, root=None, force=False, delay=2.0):
    """Ingest one registered norm from a saved file, a URL, or its SCIJ id.
    Returns (dir, units, problems). Refuses to write when the title check
    fails unless force is set; other problems are written as warnings."""
    norm = registry_entry(norm_id, root)
    if file:
        lines, raw = read_source(file)
        src_url = url or norm.get("source_url", "")
    else:
        src_url = url or norm.get("source_url") or (
            SCIJ_TEXT_URL.format(nrm=norm["scij_nrm"], version=norm.get("scij_version", 0)) if norm.get("scij_nrm") else ""
        )
        if not src_url:
            raise ValueError(f"{norm_id}: no file, url, source_url or scij_nrm")
        time.sleep(delay)  # be gentle with public servers
        raw = fetch(src_url)
        tmp = Path(root or LAWS_DIR) / ".cache"
        tmp.mkdir(exist_ok=True)
        cached = tmp / (norm_id + (".pdf" if raw[:4] == b"%PDF" else ".html"))
        cached.write_bytes(raw)
        lines, _ = read_source(cached)
    source = {
        "url": src_url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": time.strftime("%Y-%m-%d"),
        "version_date": find_version_date(lines),
    }
    parsed = parse_units(lines, norm_id, norm.get("start_pattern"))
    problems = validate(parsed, norm.get("match_title"), lines)
    if any(p.startswith("title") or p == "no units found" for p in problems) and not force:
        raise ValueError(f"{norm_id}: refusing to write: {problems}")
    units = build_units(parsed, norm, source)
    return write_norm(norm, units, source, problems, root), units, problems
