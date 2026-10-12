"""BM25 search over the corpus with an in-memory SQLite FTS5 index.

The corpus is small, so the index is rebuilt on every start: no generated
files to keep in sync. Accents are folded and Spanish words are crudely
stemmed, so "facturas" finds "factura" and "exportacion" finds "exportación".
"""

import re
import sqlite3

from .corpus import chunks_of, load_documents
from .laws import load_norms, load_units

STOPWORDS = set(
    """a al algo como con cual cuales cuando cuanto de del donde el ella en es
    esta este esto la las le lo los me mi mis o para pero por que se si sin
    sobre su sus te tiene tengo un una uno y ya the of to and in is for what
    how do does i my on are be""".split()
)


def fold(s):
    table = str.maketrans("áéíóúüñ", "aeiouun")
    return s.lower().translate(table)


def match_expression(q):
    terms = [t for t in re.findall(r"\w+", fold(q)) if t not in STOPWORDS and len(t) > 1]
    # Exact terms plus stems (last 2 chars dropped) so exact hits score higher.
    stems = {t[: max(4, len(t) - 2)] for t in terms if len(t) > 5}
    return " OR ".join(f'"{t}"*' for t in sorted(set(terms) | stems))


# Column weights for bm25(): title, section heading, section keywords,
# document keywords, body text.
W_TITLE, W_SECTION, W_SECTION_KW, W_DOC_KW, W_TEXT = 1.0, 2.0, 4.0, 0.5, 1.0
# For law units: norm title, Título/Capítulo path, epígrafe, article text, reform notes.
W_LAW_TITLE, W_LAW_PATH, W_LAW_HEADING, W_LAW_TEXT, W_LAW_NOTES = 0.5, 1.0, 2.0, 1.0, 0.2


def unit_lookup_id(norm, article):
    a = fold(article).strip().rstrip(".")
    kind = "trans" if a.startswith("trans") else "art"
    a = re.sub(r"^(transitorio|trans\.?|articulo|art\.?)\s*", "", a).strip()
    a = re.sub(r"[°º]", "", a)
    if kind == "trans":
        a = a.upper() if not a.isdigit() else a
        return f"{norm}:trans-{a}"
    a = re.sub(r"\s+", "-", a.lstrip("0") or "0")
    return f"{norm}:art-{a}"


class KnowledgeBase:
    def __init__(self, root=None, laws_root=None):
        self.docs = {d.id: d for d in load_documents(root)}
        self.chunks = {}
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute(
            """CREATE VIRTUAL TABLE fts USING fts5(chunk_id UNINDEXED, topic UNINDEXED,
            title, section, section_keywords, doc_keywords, text, tokenize='unicode61 remove_diacritics 2')"""
        )
        for doc in self.docs.values():
            for c in chunks_of(doc):
                self.chunks[c.chunk_id] = c
                # Spanish keywords let Spanish queries reach sections written in
                # English. Section keywords pick the section; the document's
                # keywords only weakly help every section of that document.
                self.db.execute(
                    "INSERT INTO fts VALUES (?,?,?,?,?,?,?)",
                    (c.chunk_id, c.topic, c.title, c.section, c.keywords, doc.keywords_es, c.text),
                )

        self._load_laws(laws_root)

    def _load_laws(self, laws_root):
        """Primary texts (laws/), one row per article or transitorio."""
        self.units = {u.id: u for u in load_units(laws_root)}
        self.norms = {n["id"]: n for n in load_norms(laws_root)}
        self.db.execute(
            """CREATE VIRTUAL TABLE law_fts USING fts5(unit_id UNINDEXED, area UNINDEXED, norm_id UNINDEXED,
            norm_title, path, heading, text, notes, tokenize='unicode61 remove_diacritics 2')"""
        )
        for u in self.units.values():
            self.db.execute(
                "INSERT INTO law_fts VALUES (?,?,?,?,?,?,?,?)",
                (u.id, u.area, u.norm_id, u.norm_title, " / ".join(u.path), u.heading, u.text, " ".join(u.notes)),
            )

    def search_law(self, query, k=5, area=None, norm=None, include_repealed=False):
        expr = match_expression(query)
        if not expr or not self.units:
            return []
        sql = "SELECT unit_id, bm25(law_fts, 0, 0, 0, ?, ?, ?, ?, ?) AS score FROM law_fts WHERE law_fts MATCH ?"
        args = [W_LAW_TITLE, W_LAW_PATH, W_LAW_HEADING, W_LAW_TEXT, W_LAW_NOTES, expr]
        if area:
            sql += " AND area = ?"
            args.append(area)
        if norm:
            sql += " AND norm_id = ?"
            args.append(norm)
        sql += " ORDER BY score LIMIT ?"
        args.append(int(k) * 3)
        hits = []
        for unit_id, score in self.db.execute(sql, args):
            u = self.units[unit_id]
            if u.status == "derogado" and not include_repealed:
                continue
            hits.append({**u.__dict__, "score": round(-score, 3)})
            if len(hits) == int(k):
                break
        return hits

    def get_unit(self, norm, article):
        """Exact lookup. `article` accepts '29', 'art 29', '29 bis', 'transitorio I'
        or a full id such as 'ley-2:art-29'."""
        uid = article if ":" in article else unit_lookup_id(norm, article)
        return self.units.get(uid)

    def topics(self):
        return sorted({d.topic for d in self.docs.values()})

    def search(self, query, k=5, topic=None):
        expr = match_expression(query)
        if not expr:
            return []
        sql = (
            "SELECT chunk_id, bm25(fts, 0, 0, ?, ?, ?, ?, ?) AS score FROM fts WHERE fts MATCH ?"
        )
        args = [W_TITLE, W_SECTION, W_SECTION_KW, W_DOC_KW, W_TEXT, expr]
        if topic:
            sql += " AND topic = ?"
            args.append(topic)
        sql += " ORDER BY score LIMIT ?"
        args.append(int(k))
        hits = []
        for chunk_id, score in self.db.execute(sql, args):
            c = self.chunks[chunk_id]
            d = self.docs[c.doc_id]
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": d.id,
                    "title": d.title,
                    "section": c.section,
                    "topic": d.topic,
                    "as_of": d.as_of,
                    "status": d.status,
                    "verified": d.verified,
                    "path": d.path,
                    "score": round(-score, 3),
                    "text": c.text,
                    "sources": d.sources,
                }
            )
        return hits


def format_hits(hits):
    if not hits:
        return "No results. Try other terms, or list_documents to browse."
    parts = []
    for h in hits:
        src = "\n".join(f"- {s.get('label', '')}: {s.get('url', '')} ({s.get('type', '')})" for s in h["sources"])
        parts.append(
            f"### {h['title']} > {h['section']}\n"
            f"[cite: {h['chunk_id']} | as of {h['as_of']} | status: {h['status']} | backed by: {h['verified']}]\n\n"
            f"{h['text']}\n\nSources:\n{src}"
        )
    return "\n\n---\n\n".join(parts)


def format_units(units):
    if not units:
        return "No matching article in the stored legal texts. Use list_norms to see what is covered."
    parts = []
    for u in units:
        label = "Artículo" if u["kind"] == "articulo" else "Transitorio"
        where = " > ".join(u["path"])
        notes = "\n".join(u["notes"])
        parts.append(
            f"### {u['norm_title']}, {label} {u['number']}\n"
            f"[cite: {u['id']} | {u['rank']} | status: {u['status']} | version {u['version_date'] or 'unknown'}"
            f" | retrieved {u['retrieved_at']}]\n"
            + (f"{where}\n" if where else "")
            + f"\n{u['text']}\n"
            + (f"\n{notes}\n" if notes else "")
            + f"\nSource: {u['source_url']}"
        )
    return "\n\n---\n\n".join(parts)
