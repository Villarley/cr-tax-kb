"""BM25 search over the corpus with an in-memory SQLite FTS5 index.

The corpus is small, so the index is rebuilt on every start: no generated
files to keep in sync. Accents are folded and Spanish words are crudely
stemmed, so "facturas" finds "factura" and "exportacion" finds "exportación".
"""

import re
import sqlite3

from .corpus import chunks_of, load_documents

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


class KnowledgeBase:
    def __init__(self, root=None):
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
