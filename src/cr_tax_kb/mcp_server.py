"""MCP server (stdio, JSON-RPC 2.0) for the Costa Rica tax knowledge base.

Standard library only, so any MCP client can launch it with plain Python:

  python3 /path/to/cr-tax-kb/src/cr_tax_kb/mcp_server.py

Tools: search_tax_kb, get_document, list_documents, get_sources (explainers in
corpus/), and search_law, get_article, list_norms (verbatim legal texts in laws/).
Resources: one per document, crtax://doc/<id> (text/markdown).
"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow running as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cr_tax_kb import __version__
    from cr_tax_kb.laws import load_registry
    from cr_tax_kb.search import KnowledgeBase, format_hits, format_units
else:
    from . import __version__
    from .laws import load_registry
    from .search import KnowledgeBase, format_hits, format_units

SUPPORTED_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = """Knowledge base of Costa Rican tax and accounting rules (IVA, income tax,
capital gains, remittances abroad, crypto, e-invoicing v4.4, TRIBU-CR, simplified
regime, CCSS for independent workers, tax calendar). Search first, then cite the
chunk id and source URL for every claim. Say when a source is secondary or a
non-binding DGT oficio, never present a bill as law, check as_of dates for yearly
amounts, and leave final positions on a return to a licensed accountant.

Verbatim legal texts (laws, decrees, reglamentos) are served article by article:
get_article for an exact article, search_law to find articles, list_norms for
coverage. Quote the article and cite its id (e.g. ley-2:art-29) and version
date. If a norm or article is not stored, say so instead of answering from memory.
Keep law (the article) separate from interpretation (explainers, oficios)."""

TOOLS = [
    {
        "name": "search_tax_kb",
        "title": "Search Costa Rica tax knowledge base",
        "description": "Search Costa Rican tax and accounting rules. Spanish or English queries. "
        "Returns matching sections with a citation id, date, status, and source URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or keywords, e.g. 'IVA exportación de servicios'"},
                "k": {"type": "integer", "description": "Max results (default 5)", "minimum": 1, "maximum": 20},
                "topic": {
                    "type": "string",
                    "description": "Optional filter: general, iva, renta, cripto, facturacion, procedimiento, ccss",
                },
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_document",
        "title": "Get a full document",
        "description": "Return one document in full (Markdown) by id, e.g. 'crypto-assets'.",
        "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "list_documents",
        "title": "List documents",
        "description": "List all documents with id, title, topic, as_of date, status and source strength.",
        "inputSchema": {"type": "object", "properties": {"topic": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_sources",
        "title": "Get sources",
        "description": "Return the source list (label, URL, type, date) for one document, or for all if no id.",
        "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


AREA_DESC = "Optional filter: laboral, ccss, tributario, contable, mercantil, general"

TOOLS += [
    {
        "name": "search_law",
        "title": "Search Costa Rican legal texts",
        "description": "Search the verbatim text of stored Costa Rican laws, decrees and reglamentos at article "
        "level. Returns articles with citation id, version date, status and source URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or keywords, e.g. 'preaviso despido'"},
                "k": {"type": "integer", "description": "Max results (default 5)", "minimum": 1, "maximum": 20},
                "area": {"type": "string", "description": AREA_DESC},
                "norm": {"type": "string", "description": "Optional norm id, e.g. 'ley-2'"},
                "include_repealed": {"type": "boolean", "description": "Include derogated articles"},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_article",
        "title": "Get one article verbatim",
        "description": "Exact article of a stored norm, e.g. norm 'ley-2' article '29', '29 bis' or 'transitorio I'.",
        "inputSchema": {
            "type": "object",
            "properties": {"norm": {"type": "string"}, "article": {"type": "string"}},
            "required": ["norm", "article"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "list_norms",
        "title": "List stored legal texts",
        "description": "Norms held as verbatim text, with version date, source and article counts, plus "
        "registered norms not ingested yet.",
        "inputSchema": {"type": "object", "properties": {"area": {"type": "string", "description": AREA_DESC}}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


class Server:
    def __init__(self, kb=None):
        self.kb = kb or KnowledgeBase()

    def handle(self, msg):
        method, params, mid = msg.get("method"), msg.get("params") or {}, msg.get("id")
        if mid is None:  # notification, e.g. notifications/initialized
            return None
        try:
            result = self.dispatch(method, params)
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {e}"}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def dispatch(self, method, params):
        if method == "initialize":
            requested = params.get("protocolVersion")
            return {
                "protocolVersion": requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0],
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "cr-tax-kb", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            return self.call_tool(params.get("name"), params.get("arguments") or {})
        if method == "resources/list":
            return {
                "resources": [
                    {
                        "uri": f"crtax://doc/{d.id}",
                        "name": d.id,
                        "title": d.title,
                        "description": f"{d.topic}, as of {d.as_of}, backed by {d.verified}",
                        "mimeType": "text/markdown",
                    }
                    for d in self.kb.docs.values()
                ]
            }
        if method == "resources/read":
            doc_id = params.get("uri", "").removeprefix("crtax://doc/")
            d = self.kb.docs.get(doc_id)
            if not d:
                raise ValueError(f"Unknown resource: {params.get('uri')}")
            return {"contents": [{"uri": params["uri"], "mimeType": "text/markdown", "text": d.body}]}
        raise KeyError(method)

    def call_tool(self, name, args):
        def text(s, error=False):
            return {"content": [{"type": "text", "text": s}], "isError": error}

        if name == "search_tax_kb":
            hits = self.kb.search(args.get("query", ""), args.get("k", 5), args.get("topic"))
            return text(format_hits(hits))
        if name == "get_document":
            d = self.kb.docs.get(args.get("id", ""))
            if not d:
                return text(f"Unknown id. Known ids: {', '.join(self.kb.docs)}", error=True)
            meta = json.dumps(d.summary(), ensure_ascii=False, indent=2)
            return text(f"{meta}\n\n{d.body}")
        if name == "list_documents":
            topic = args.get("topic")
            rows = [d.summary() for d in self.kb.docs.values() if not topic or d.topic == topic]
            for r in rows:
                r.pop("sources")
                r.pop("keywords_es")
            return text(json.dumps(rows, ensure_ascii=False, indent=2))
        if name == "get_sources":
            ids = [args["id"]] if args.get("id") else list(self.kb.docs)
            out = {i: self.kb.docs[i].sources for i in ids if i in self.kb.docs}
            if not out:
                return text("Unknown id.", error=True)
            return text(json.dumps(out, ensure_ascii=False, indent=2))
        if name == "search_law":
            hits = self.kb.search_law(
                args.get("query", ""), args.get("k", 5), args.get("area"), args.get("norm"),
                bool(args.get("include_repealed")),
            )
            return text(format_units(hits))
        if name == "get_article":
            norm = args.get("norm", "")
            if norm not in self.kb.norms:
                return text(f"Norm '{norm}' is not stored. Stored: {', '.join(self.kb.norms) or 'none yet'}", error=True)
            u = self.kb.get_unit(norm, str(args.get("article", "")))
            if not u:
                return text(f"Article not found in {norm}. Check the number, or search_law with norm={norm}.", error=True)
            return text(format_units([u.__dict__]))
        if name == "list_norms":
            area = args.get("area")
            stored = [n for n in self.kb.norms.values() if not area or n.get("area") == area]
            pending = [
                {k: r[k] for k in ("id", "title", "area", "phase")}
                for r in load_registry()
                if r["id"] not in self.kb.norms and (not area or r["area"] == area)
            ]
            return text(json.dumps({"stored": stored, "registered_not_ingested": pending}, ensure_ascii=False, indent=2))
        return text(f"Unknown tool: {name}", error=True)


def main():
    server = Server()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = server.handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
